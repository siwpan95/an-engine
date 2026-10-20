"""存档版本迁移测试 —— 钉住 v0 历史存档可读、高版本拒载、迁移链可扩展。

对应 P0-3：``allin_engine.core.world_serial`` 加了 schema 头与迁移链。

口径：本仓测试栈**不依赖 pytest**（见 ``test_trpg.py`` 开头说明），
断言一律用 ``assert`` / 显式 ``_expect_raises``。
"""

from allin_engine.core import Component
from allin_engine.core.world_serial import (
    SAVE_SCHEMA_NAME,
    SAVE_SCHEMA_VERSION,
    SaveFormatError,
    SerializableWorld,
    migrate,
    register_migration,
    schema_version_of,
)


class Pos(Component):
    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.x = x
        self.y = y


class Ghost(Component):
    def __init__(self, name: str = "?"):
        self.name = name


def _expect_raises(exc_type, fn, contains=None):
    """pytest.raises 的等价物：返回异常实例，顺带可断言消息片段。"""
    try:
        fn()
    except exc_type as exc:
        if contains is not None and contains not in str(exc):
            raise AssertionError(
                f"异常消息不含 {contains!r}，实际为：{exc}"
            ) from None
        return exc
    raise AssertionError(f"预期抛出 {exc_type.__name__}，但没有抛出")


def _legacy_payload():
    """模拟引擎 1.0.0 之前的存档：没有 schema 头。"""
    return {
        "entities": [
            {"eid": "player", "id": 0, "components": {"Pos": {"x": 3.0, "y": 4.0}}},
            {"eid": "npc", "id": 1, "components": {"Ghost": {"name": "影子"}}},
        ],
        "systems": [],
        "data": {"chapter": 2},
    }


def test_to_dict_carries_schema():
    w = SerializableWorld(component_catalog={"Pos": Pos})
    w.create_entity("player").add(Pos(1, 2))
    data = w.to_dict()
    assert data["schema"]["name"] == SAVE_SCHEMA_NAME
    assert data["schema"]["version"] == SAVE_SCHEMA_VERSION


def test_legacy_save_without_schema_loads():
    w = SerializableWorld.from_dict(_legacy_payload(), component_catalog={"Pos": Pos})
    assert w.load_report["migrated_from"] == 0
    assert w.load_report["migrated_to"] == SAVE_SCHEMA_VERSION
    assert w.load_report["steps"] == ["v0->v1"]
    e = w.get_entity("player")
    assert e is not None
    assert e.get(Pos).x == 3.0 and e.get(Pos).y == 4.0
    assert w.get_data("chapter") == 2


def test_unknown_component_is_reported_not_silent():
    w = SerializableWorld.from_dict(_legacy_payload(), component_catalog={"Pos": Pos})
    assert w.load_report["unknown_components"] == ["Ghost"]


def test_legacy_payload_missing_keys():
    w = SerializableWorld.from_dict({"data": {"a": 1}}, component_catalog={})
    assert w.entity_count() == 0
    assert w.get_data("a") == 1
    assert w.load_report["migrated_from"] == 0


def test_future_version_rejected():
    data = {"schema": {"name": SAVE_SCHEMA_NAME, "version": 99}, "entities": []}
    _expect_raises(
        SaveFormatError, lambda: SerializableWorld.from_dict(data), "高于引擎支持"
    )


def test_schema_name_mismatch_rejected():
    data = {"schema": {"name": "other-game/world", "version": 1}, "entities": []}
    _expect_raises(
        SaveFormatError, lambda: SerializableWorld.from_dict(data), "schema 名不匹配"
    )


def test_bad_version_type_rejected():
    data = {"schema": {"name": SAVE_SCHEMA_NAME, "version": "v1"}}
    _expect_raises(SaveFormatError, lambda: schema_version_of(data))


def test_missing_migration_path_raises():
    _expect_raises(
        SaveFormatError, lambda: migrate(_legacy_payload(), target=5), "缺少 v1 -> v2"
    )


def test_migrate_chain_to_target_2():
    def v1_to_v2(d):
        out = dict(d)
        out["data"] = dict(out.get("data", {}), upgraded=True)
        return out

    report = {}
    out = migrate(_legacy_payload(), target=2, migrations={1: v1_to_v2}, report=report)
    assert report["steps"] == ["v0->v1", "v1->v2"]
    assert out["schema"]["version"] == 2
    assert out["data"]["upgraded"] is True


def test_from_dict_accepts_custom_migration():
    """下游可以把旧组件名改写成新名，而不必改引擎。"""

    def rename(d):
        out = dict(d)
        ents = []
        for ed in out.get("entities", []):
            ed = dict(ed)
            comps = dict(ed.get("components", {}))
            if "Ghost" in comps:
                comps["Pos"] = {"x": 0.0, "y": 0.0}
                comps.pop("Ghost")
            ed["components"] = comps
            ents.append(ed)
        out["entities"] = ents
        return out

    w = SerializableWorld.from_dict(
        _legacy_payload(), component_catalog={"Pos": Pos}, migrations={0: rename}
    )
    assert w.load_report["unknown_components"] == []
    assert w.get_entity("npc").get(Pos) is not None


def test_register_migration_rejects_duplicate():
    _expect_raises(ValueError, lambda: register_migration(0)(lambda d: d))


def test_register_migration_rejects_skip():
    _expect_raises(ValueError, lambda: register_migration(7, to_version=9)(lambda d: d))


def test_migration_returning_non_dict_rejected():
    _expect_raises(
        SaveFormatError,
        lambda: migrate(_legacy_payload(), target=2, migrations={1: lambda d: ["nope"]}),
    )
