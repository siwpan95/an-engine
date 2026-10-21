"""
TypeClass：数据 / 行为分离 + CmdSet 合并
========================================

来源：Evennia（思路档，BSD-3-Clause）。
借用范围：**思路**（自研实现其「对象的数据与行为解耦、命令集按优先级合并去重」
概念，未搬 Evennia 源码、未照抄命名 / 结构）。

Evennia 的核心设计是：游戏对象持有一个 *typeclass*（决定行为的 Python 类），
而它的可变数据存放在独立的存储里（与类解耦）。命令则组织成 *CmdSet*，
多个 CmdSet 可按规则合并（同 key 的命令按优先级去重，高优先级胜出）。
本模块自研这两层能力。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


class TypeClass:
    """数据 / 行为分离的基类。

    行为由子类方法提供；**可变数据**统一存放在 ``db``（一个可序列化字典），
    与具体类解耦——这正是 Evennia 把"属性存储"和"类逻辑"分开的思想。

    用法::
        class Sword(TypeClass):
            typeclass_name = "sword"
            def describe(self): return f"一把{self.get('material')}剑"

        sword = Sword("excalibur", {"material": "秘银", "atk": 12})
        sword.set("atk", 15)
    """

    #: 类级标识（子类覆盖）
    typeclass_name: str = "base"

    def __init__(self, key: str, data: Optional[dict] = None) -> None:
        self.key = key
        # 可变数据独立于类：增删改不触碰类定义
        self.db: Dict[str, object] = dict(data or {})

    # ── 数据访问（与行为解耦） ────────────────────────
    def get(self, name: str, default: object = None) -> object:
        return self.db.get(name, default)

    def set(self, name: str, value: object) -> None:
        self.db[name] = value

    def has(self, name: str) -> bool:
        return name in self.db

    def delete(self, name: str) -> bool:
        return self.db.pop(name, None) is not None

    def to_dict(self) -> dict:
        return {"key": self.key, "typeclass": self.typeclass_name, "db": dict(self.db)}


@dataclass
class Cmd:
    """一条命令：名称 + 优先级 + 处理函数。``key`` 是去重键（默认等于 name）。"""

    name: str
    priority: int = 0
    func: Optional[Callable] = None
    key: str = ""

    def __post_init__(self) -> None:
        if not self.key:
            self.key = self.name

    def __call__(self, *args, **kwargs):
        if self.func is not None:
            return self.func(*args, **kwargs)
        return None


class CmdSet:
    """一组命令。支持按「命令优先级」合并多个 CmdSet 并去重。"""

    def __init__(self, name: str = "cmdset", priority: int = 0) -> None:
        self.name = name
        self.priority = priority
        self._cmds: Dict[str, Cmd] = {}

    def add(self, cmd: Cmd) -> "CmdSet":
        """加入命令；同名（key）命令保留优先级更高者。"""
        existing = self._cmds.get(cmd.key)
        if existing is None or cmd.priority >= existing.priority:
            self._cmds[cmd.key] = cmd
        return self

    def remove(self, key: str) -> bool:
        return self._cmds.pop(key, None) is not None

    def get(self, key: str) -> Optional[Cmd]:
        return self._cmds.get(key)

    @property
    def commands(self) -> List[Cmd]:
        return list(self._cmds.values())

    def keys(self) -> List[str]:
        return list(self._cmds.keys())

    def merge(self, *others: "CmdSet") -> "CmdSet":
        """多个命令集按「命令优先级」合并去重：同名命令保留优先级更高者。

        合并秩（CmdSet.priority）仅用于整体排序说明，逐命令去重仍以命令自身
        的 ``priority`` 为准——这样来自高优先级 CmdSet 的命令不会无脑覆盖一切，
        而是逐条按命令优先级裁决（与 Evennia 逐命令合并语义一致）。
        """
        merged = CmdSet(f"{self.name}+merged")
        for cs in (self, *others):
            for cmd in cs._cmds.values():
                merged.add(cmd)
        return merged
