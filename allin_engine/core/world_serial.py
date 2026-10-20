"""World 直接序列化 —— 含**存档版本迁移**。

提供 SerializableWorld(World)，对齐引擎既有 to_dict / from_dict 契约，
可直接交给 SaveLoadManager 存档 / 读档，无需项目侧自行 to_dict。

纯新增模块，不修改 allin_engine.core.ecs 的 World 类。

存档格式带 ``schema`` 头：

    {"schema": {"name": "allin-engine/world", "version": 1},
     "entities": [...], "systems": [...], "data": {...}}

没有 ``schema`` 头的历史存档按 **v0** 处理，由内置迁移 ``v0 -> v1`` 补齐结构后
再交给反序列化；版本号高于引擎支持范围时**拒载**（而不是静默丢字段）。

迁移函数的形态是 ``fn(data: dict) -> dict``，逐版本串联。下游项目有自己的
存档 schema 时，用 ``register_migration()`` 或给 ``from_dict(..., migrations=...)``
传一层覆盖表即可，不必改引擎。
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from allin_engine.core.ecs import World, Component, System

#: 存档 schema 名（与引擎发版解耦，改结构必须升 version）
SAVE_SCHEMA_NAME = "allin-engine/world"

#: 引擎当前支持的存档版本
SAVE_SCHEMA_VERSION = 1

#: 迁移函数：接收上一版 data，返回下一版 data（可原地改，也可返回新 dict）
Migration = Callable[[dict], dict]


class SaveFormatError(ValueError):
    """存档不可识别、版本过新、或缺少迁移路径。"""


#: {from_version: (to_version, fn)}
_MIGRATIONS: Dict[int, Tuple[int, Migration]] = {}


def register_migration(from_version: int, to_version: Optional[int] = None):
    """注册 ``from_version -> from_version + 1`` 的迁移（可作装饰器用）。

    参数：
        from_version: 迁移的起点版本
        to_version:   终点版本，省略即 ``from_version + 1``；目前只支持逐版本
                      递进（跨版本请分多次注册），跨版本注册会直接报错。

    用法：
        @register_migration(0)
        def _v0_to_v1(data):
            ...
    """

    def deco(fn: Migration) -> Migration:
        target = from_version + 1 if to_version is None else to_version
        if target != from_version + 1:
            raise ValueError(
                f"暂不支持跨版本迁移：{from_version} -> {target}；"
                f"请只注册 {from_version} -> {from_version + 1}"
            )
        if from_version in _MIGRATIONS:
            raise ValueError(f"版本 {from_version} 的迁移已注册，不允许覆盖")
        _MIGRATIONS[from_version] = (target, fn)
        return fn

    return deco


@register_migration(0)
def _migrate_0_to_1(data: dict) -> dict:
    """v0（无 schema 头的历史存档）-> v1。

    只做**结构补齐**，不猜测语义：
      - 缺 ``entities`` / ``systems`` / ``data`` 时补空容器；
      - 实体缺 ``components`` 时补空字典（组件解析仍走 catalog，未知组件进
        load_report，不静默改写数据）。
    """
    out = dict(data or {})
    out.setdefault("entities", [])
    out.setdefault("systems", [])
    out.setdefault("data", {})
    for ed in out["entities"]:
        if isinstance(ed, dict):
            ed.setdefault("components", {})
    return out


def schema_version_of(data: Any) -> int:
    """读出存档版本；无 schema 头一律视为 v0。"""
    if not isinstance(data, dict):
        raise SaveFormatError(f"存档根节点必须是 dict，收到 {type(data).__name__}")
    schema = data.get("schema")
    if not isinstance(schema, dict):
        return 0
    version = schema.get("version", 0)
    if not isinstance(version, int) or version < 0:
        raise SaveFormatError(f"非法存档版本号：{version!r}")
    name = schema.get("name")
    if name not in (None, SAVE_SCHEMA_NAME):
        raise SaveFormatError(
            f"存档 schema 名不匹配：期望 {SAVE_SCHEMA_NAME!r}，收到 {name!r}"
        )
    return version


def migrate(
    data: Any,
    target: int = SAVE_SCHEMA_VERSION,
    migrations: Optional[Dict[int, Migration]] = None,
    report: Optional[dict] = None,
) -> dict:
    """把存档逐版本迁移到 ``target``。

    参数：
        data:       原始存档（dict）
        target:     目标版本，默认引擎当前版本
        migrations: 额外的 ``{from_version: fn}`` 覆盖表（下游项目用）
        report:     出参；写入 ``migrated_from`` / ``migrated_to`` / ``steps``

    异常：
        SaveFormatError —— 版本过新、缺少迁移路径、迁移函数返回非法结构
    """
    table: Dict[int, Migration] = {v: fn for v, (_to, fn) in _MIGRATIONS.items()}
    if migrations:
        table.update(migrations)

    start = schema_version_of(data)
    if start > target:
        raise SaveFormatError(
            f"存档版本 v{start} 高于引擎支持的 v{target}："
            f"请升级引擎后再读取，或导出为旧版存档"
        )

    report = report if report is not None else {}
    report.setdefault("migrated_from", start)
    steps: List[str] = report.setdefault("steps", [])

    current = start
    out = dict(data)
    while current < target:
        fn = table.get(current)
        if fn is None:
            raise SaveFormatError(
                f"缺少 v{current} -> v{current + 1} 的迁移函数："
                f"请在 register_migration({current}) 里补上，或显式传 migrations="
            )
        out = fn(out)
        if not isinstance(out, dict):
            raise SaveFormatError(
                f"迁移 v{current} -> v{current + 1} 返回了 {type(out).__name__}，必须是 dict"
            )
        steps.append(f"v{current}->v{current + 1}")
        current += 1

    out = dict(out)
    out["schema"] = {"name": SAVE_SCHEMA_NAME, "version": target}
    report["migrated_to"] = target
    return out


class SerializableWorld(World):
    """可序列化的 World。

    catalog 注册组件 / 系统类（按 __name__），反序列化时据此重建实例。

    用法：
        world = SerializableWorld(component_catalog={Pos, Health}, system_catalog={MoveSys})
        world.create_entity("player").add(Pos(1, 2)).add(Health(100))
        world.add_system(MoveSys())
        mgr.save(world, slot=0)                         # SaveLoadManager 直接吃
        data = mgr.load(0)
        world2 = SerializableWorld.from_dict(data, component_catalog, system_catalog)

    读档后 ``world2.load_report`` 给出这次读取的可观测信息：
        {"migrated_from": 0, "migrated_to": 1, "steps": ["v0->v1"],
         "unknown_components": ["Foo"], "unknown_systems": ["Bar"]}
    """

    def __init__(
        self,
        component_catalog: Optional[Dict[str, Type[Component]]] = None,
        system_catalog: Optional[Dict[str, Type[System]]] = None,
    ):
        super().__init__()
        self._comp_catalog: Dict[str, Type[Component]] = dict(component_catalog or {})
        self._sys_catalog: Dict[str, Type[System]] = dict(system_catalog or {})
        #: 最近一次 from_dict 的报告（新建的 world 为 None）
        self.load_report: Optional[dict] = None

    # ── 序列化 ──
    def to_dict(self) -> dict:
        entities: List[dict] = []
        for e in self._entities_by_id.values():
            comps: Dict[str, Any] = {}
            for ctype, comp in e.components.items():
                if dataclasses.is_dataclass(comp):
                    comps[ctype.__name__] = dataclasses.asdict(comp)
                else:
                    comps[ctype.__name__] = getattr(comp, "__dict__", comp)
            entities.append({"eid": e.eid, "id": e.id, "components": comps})

        systems: List[dict] = []
        for s in self.systems:
            sname = type(s).__name__
            sstate = s.to_dict() if hasattr(s, "to_dict") else None
            systems.append({"name": sname, "priority": getattr(s, "priority", 100), "state": sstate})

        return {
            "schema": {"name": SAVE_SCHEMA_NAME, "version": SAVE_SCHEMA_VERSION},
            "entities": entities,
            "systems": systems,
            "data": self._data,
        }

    # ── 反序列化 ──
    @classmethod
    def from_dict(
        cls,
        data: dict,
        component_catalog: Optional[Dict[str, Type[Component]]] = None,
        system_catalog: Optional[Dict[str, Type[System]]] = None,
        migrations: Optional[Dict[int, Migration]] = None,
    ) -> "SerializableWorld":
        report: dict = {"unknown_components": [], "unknown_systems": []}
        data = migrate(data, migrations=migrations, report=report)

        world = cls(component_catalog=component_catalog, system_catalog=system_catalog)
        comp_cat = world._comp_catalog
        sys_cat = world._sys_catalog

        # 重建实体 + 组件
        for ed in data.get("entities", []):
            e = world.create_entity(ed.get("eid"))
            for cname, cval in ed.get("components", {}).items():
                ctype = comp_cat.get(cname)
                if ctype is None:
                    if cname not in report["unknown_components"]:
                        report["unknown_components"].append(cname)
                    continue
                try:
                    comp = ctype(**cval) if isinstance(cval, dict) else ctype(cval)
                except Exception:
                    comp = ctype(**(cval or {}))
                e.add(comp)

        # 重建系统
        for sd in data.get("systems", []):
            stype = sys_cat.get(sd.get("name"))
            if stype is None:
                if sd.get("name") not in report["unknown_systems"]:
                    report["unknown_systems"].append(sd.get("name"))
                continue
            try:
                s = stype() if not sd.get("state") else stype(**(sd.get("state") or {}))
            except Exception:
                s = stype()
            world.add_system(s)

        # 全局数据
        world._data.update(data.get("data", {}) or {})
        world.load_report = report
        return world
