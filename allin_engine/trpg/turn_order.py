"""
回合制：状态/增益减益叠层与行动速度排序
=========================================

来源：RPG Maker MV **1.3.x** 快照（``rpg_objects.js`` / ``rpg_managers.js``）。
许可：MIT（版权 KADOKAWA / YOJI OJIMA）。
借用范围：**算法 + 代码**（只对 1.3.x 快照；未参考 1.6+ / MZ 的 ``rmmz_*``）。

本文件只借 MV 三层算法 / 结构，未复制其源码字符串：

1. 状态优先级互斥（``Game_BattlerBase#isStateRestrict``）：
   "若已存在 **priority 更高** 且 ``restriction>0`` 的状态，则新状态不可叠加"。
2. 状态可叠层（增益 buff 的层数机制 ``Game_BattlerBase#_buffs``）：
   同类效果最多叠 ``max_stacks`` 层，每层带来 ``step`` 数值。
3. 行动速度排序（``BattleManager`` 的先攻顺序）：按 ``speed`` 降序，
   ``speed = agi + base`` 再叠加状态带来的速度修正（haste / slow），
   对应 MV ``Game_Battler#speed`` 由 ``agi`` 派生 + ``BattleManager#makeSpeed`` 修正。

> 6 之后若 MV 改为 ``rmmz_*`` 实现，本实现不跟随；本仓只对标 1.3.x 行为。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StateDef:
    """状态 / 增益定义（对应 MV 数据库 States 的字段子集）。

    Attributes:
        id:             状态 id（1 通常保留给"死亡"这类最高限制）
        name:           显示名
        priority:       优先级，越大越优先；决定"限制互斥"的胜负
        restriction:    行动限制等级（0=无限制；>0 表示限制行动，MV 的 restriction）
        buff:           是否为增益（区别于负面状态）
        min_turns:      最短持续回合
        max_turns:      最长持续回合（MV 在 [min,max] 间随机取整）
        remove_by_damage_chance: 受击时解除的概率（MV 的 chanceByDamage）
        step:           每层带来的数值幅度（如攻击 +1 / 层）
        speed_mod:      每层对行动速度的影响（haste 为正、slow 为负）
        max_stacks:     最多可叠加层数
    """

    id: int
    name: str = ""
    priority: int = 50
    restriction: int = 0
    buff: bool = False
    min_turns: int = 1
    max_turns: int = 1
    remove_by_damage_chance: float = 0.0
    step: int = 1
    speed_mod: int = 0
    max_stacks: int = 1

    def __post_init__(self) -> None:
        if self.name == "":
            self.name = f"state_{self.id}"
        if self.max_stacks < 1:
            self.max_stacks = 1
        if self.max_turns < self.min_turns:
            self.max_turns = self.min_turns


@dataclass
class StatusInstance:
    """某战斗单位身上的一份「激活状态 / 增益」。"""

    def_id: int
    stacks: int = 1
    turns_left: int = 1

    def __post_init__(self) -> None:
        if self.stacks < 1:
            self.stacks = 1


def _pick_turns(d: StateDef, rng: Optional[Any] = None) -> int:
    """在 [min_turns, max_turns] 间取一个持续回合数。

    MV 用 ``Math.random()`` 随机取整；为让测试可复现，缺省取 ``min_turns``，
    有 ``rng``（含 ``.random()`` 方法）时再随机——自研确定性策略，不依赖 MV 源码。
    """
    if d.max_turns <= d.min_turns:
        return d.min_turns
    if rng is not None:
        return d.min_turns + int(rng.random() * (d.max_turns - d.min_turns + 1))
    return d.min_turns


class StatusContainer:
    """一个战斗单位的「激活状态 / 增益」集合，承载叠层与互斥规则。"""

    def __init__(self, defs: Dict[int, StateDef]):
        self._defs = defs
        self._active: Dict[int, StatusInstance] = {}

    # ── 互斥判定（MV isStateRestrict 语义） ──────────────
    def is_addable(self, def_id: int) -> bool:
        """新状态能否叠加。

        MV 规则：若存在 **priority 更高** 且 ``restriction>0`` 的已有状态，
        则新状态不可叠加（被更重的限制挡住）。priority 相等可叠加（用 ``>``）。
        """
        d = self._defs[def_id]
        if d.restriction > 0:
            for other in self._active.values():
                od = self._defs[other.def_id]
                if od.restriction > 0 and od.priority > d.priority:
                    return False
        return True

    # ── 施加 ────────────────────────────────────────────
    def apply(self, def_id: int, stacks: int = 1, rng: Optional[Any] = None) -> bool:
        """施加状态 / 增益。返回是否成功（被互斥挡住则返回 False）。

        - 已存在同类：层数累加至 ``max_stacks``，并刷新持续回合；
        - 不存在：新建实例，持续回合取 [_pick_turns]。
        """
        d = self._defs[def_id]
        if not self.is_addable(def_id):
            return False
        inst = self._active.get(def_id)
        if inst is None:
            self._active[def_id] = StatusInstance(
                def_id, min(stacks, d.max_stacks), _pick_turns(d, rng)
            )
        else:
            inst.stacks = min(inst.stacks + stacks, d.max_stacks)
            inst.turns_left = max(inst.turns_left, d.min_turns)
        return True

    # ── 回合推进 ────────────────────────────────────────
    def tick(self) -> List[int]:
        """每个回合末递减持续回合；返回本回合到期的状态 id 列表。"""
        expired: List[int] = []
        for def_id, inst in list(self._active.items()):
            inst.turns_left -= 1
            if inst.turns_left <= 0:
                expired.append(def_id)
                del self._active[def_id]
        return expired

    # ── 查询 ────────────────────────────────────────────
    def has(self, def_id: int) -> bool:
        return def_id in self._active

    def active_states(self) -> List[int]:
        return list(self._active.keys())

    def restriction_level(self) -> int:
        """当前最高的行动限制等级（0 = 无限制）。"""
        lvl = 0
        for inst in self._active.values():
            lvl = max(lvl, self._defs[inst.def_id].restriction)
        return lvl

    def is_restricted(self) -> bool:
        return self.restriction_level() > 0

    def magnitude(self, def_id: int) -> int:
        """该状态的当前数值幅度 = 层数 × step。"""
        inst = self._active.get(def_id)
        if inst is None:
            return 0
        return inst.stacks * self._defs[def_id].step

    def speed_modifier(self) -> int:
        """所有激活状态对行动速度的修正之和（haste/slow）。"""
        total = 0
        for inst in self._active.values():
            total += inst.stacks * self._defs[inst.def_id].speed_mod
        return total

    def clear(self) -> None:
        self._active.clear()

    def __len__(self) -> int:
        return len(self._active)


@dataclass
class Combatant:
    """排行单位：仅需 agi / base_speed / 可选状态容器即可参与先攻排序。"""

    id: str
    agi: int = 10
    base_speed: int = 0
    statuses: Optional[StatusContainer] = None

    def speed(self) -> int:
        """行动速度 = 基础速度 + 敏捷 + 状态修正（对应 MV Game_Battler#speed）。"""
        s = self.base_speed + self.agi
        if self.statuses is not None:
            s += self.statuses.speed_modifier()
        return s


def order_by_speed(combatants: List[Combatant]) -> List[Combatant]:
    """按行动速度降序排先攻顺序（同速按敏捷降序、再按 id 稳定）。

    对应 MV ``BattleManager`` 按速度决定行动顺序；纯函数，不改动入参。
    """
    return sorted(
        combatants,
        key=lambda c: (c.speed(), c.agi, c.id),
        reverse=True,
    )
