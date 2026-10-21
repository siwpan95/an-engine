"""
ECS 架构核心 — 类型安全版本
==============================

融合 carimara_py 的 ECS 核心设计与扩展功能：
- 实体使用自增整数 ID 作为主键，字符串 eid 为可选标识
- 全局数据共享（set_data / get_data）
- 组件查询、生成器遍历、链式调用
- TypeVar 泛型类型安全、延迟排序
"""

from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from typing import (Any, Callable, ClassVar, Dict, List, Optional, Sequence, Set,
                    Tuple, Type, TypeVar)

from .event_bus import EventBus

T = TypeVar("T")
C = TypeVar("C", bound="Component")

# ─── 系统相位 ───────────────────────────────────────
#: 相位顺序固定为 pre → update → post，**优先于 priority**。
#: priority 只在同一相位内部决定先后。
PHASE_PRE = "pre"
PHASE_UPDATE = "update"
PHASE_POST = "post"
PHASE_ORDER: Tuple[str, ...] = (PHASE_PRE, PHASE_UPDATE, PHASE_POST)

# ─── Unity 生命周期相位别名（B 类，仅思路 / 文档级语义）──────────
# 来源：Unity ``UnityCsReference``（B 类 Companion License，**仅公开文档级语义**）。
# 借用范围：**思路**——不复制代码、不做功能对标清单、不改下方相位执行逻辑。
# 相位逻辑来自 bevy_ecs（已落地于 §二点九），此处只补一组「可读映射」别名，
# 便于把既有 pre/update/post 对应到 Unity 的 Awake/Start/FixedUpdate/Update/LateUpdate。
PHASE_AWAKE = PHASE_PRE            # 初始化，类比 Unity Awake
PHASE_START = PHASE_PRE           # 首次更新前，类比 Unity Start（与 Awake 同落入 pre）
PHASE_FIXED_UPDATE = PHASE_UPDATE # 固定步长更新，类比 Unity FixedUpdate
PHASE_LATE_UPDATE = PHASE_POST    # 更新后同步/清理，类比 Unity LateUpdate
#: 纯文档映射：既有相位 → Unity 风格标签（不参与任何逻辑判断）
UNITY_PHASE_MAP: Dict[str, str] = {
    PHASE_PRE: "Awake/Start",
    PHASE_UPDATE: "FixedUpdate/Update",
    PHASE_POST: "LateUpdate",
}

# ─── 实体 ID 分配 ───────────────────────────────────
# World 持有实例级自增计数器（见 World._next_entity_id），
# 保证不同 World 的实体 ID 互相隔离。
# 以下模块级计数器仅作为「脱离 World 直接构造 Entity」时的回退，
# 正式实体务必通过 World.create_entity 创建。

_orphan_entity_id: int = 0


def _next_orphan_id() -> int:
    """脱离 World 直接构造 Entity 时使用的回退 ID（非全局 ECS 计数器）。"""
    global _orphan_entity_id
    _orphan_entity_id += 1
    return _orphan_entity_id


# ─── Component ─────────────────────────────────────────

class Component(ABC):
    """
    所有组件的抽象基类。

    推荐使用 @dataclass 继承以获得类型安全的组件：

        @dataclass
        class Position(Component):
            x: int = 0
            y: int = 0

        @dataclass
        class Health(Component):
            value: int = 100
            max_value: int = 100
    """


def is_component(obj: Any) -> bool:
    """检查对象是否为 Component 实例。"""
    return isinstance(obj, Component)


# ─── Entity ────────────────────────────────────────────

class Entity:
    """
    实体 — 组件的容器。

    使用自增整数 ``id`` 作为主键，字符串 ``eid`` 作为可选逻辑标识。
    支持链式调用和 __slots__ 内存优化。

    属性：
        id: 自增整数主键（全局唯一）
        eid: 可选的字符串标识（如 "player", "door_1"）
        components: 以组件类为键的组件字典
    """

    __slots__ = ("id", "eid", "components", "_world", "_generation", "_alive")

    def __init__(self, eid: Optional[str] = None, *, entity_id: Optional[int] = None) -> None:
        # id 优先由 World.create_entity 显式传入；脱离 World 直接构造时回退到模块级计数器
        self.id: int = entity_id if entity_id is not None else _next_orphan_id()
        self.eid: Optional[str] = eid
        self.components: Dict[Type[Component], Component] = {}
        # 归属的 World（游离实体为 None）；用于组件变动时同步倒排索引
        self._world: Optional["World"] = None
        # 代际：每次被移出世界 +1。旧句柄靠它识别"这个 id 已经不是我认识的那个实体了"
        self._generation: int = 0
        self._alive: bool = True

    @property
    def generation(self) -> int:
        """实体代际（移出世界时递增）。"""
        return self._generation

    @property
    def is_alive(self) -> bool:
        """是否仍挂在某个 World 上（被移除/被同名 eid 顶替后为 False）。"""
        return self._alive

    def add(self, comp: Component) -> "Entity":
        """添加组件，返回 self 支持链式调用。

        用法：
            entity.add(Position(10, 20)).add(Health(100))
        """
        ctype = type(comp)
        self.components[ctype] = comp
        if self._world is not None:
            self._world._index_add(ctype, self)
        return self

    def get(self, comp_type: Type[T]) -> Optional[T]:
        """按类型获取组件，类型安全。

        用法：
            pos = entity.get(Position)  # 返回 Optional[Position]
        """
        return self.components.get(comp_type)  # type: ignore[return-value]

    def has(self, comp_type: Type[Component]) -> bool:
        """检查是否拥有指定组件。"""
        return comp_type in self.components

    def has_all(self, *comp_types: Type[Component]) -> bool:
        """检查是否同时拥有所有指定组件。"""
        return all(t in self.components for t in comp_types)

    def has_any(self, *comp_types: Type[Component]) -> bool:
        """检查是否拥有任意一个指定组件。"""
        return any(t in self.components for t in comp_types)

    def remove(self, comp_type: Type[Component]) -> Optional[Component]:
        """移除组件，返回被移除的组件或 None。"""
        comp = self.components.pop(comp_type, None)
        if comp is not None and self._world is not None:
            self._world._index_discard(comp_type, self)
        return comp

    def clear_components(self) -> None:
        """移除所有组件。"""
        if self._world is not None:
            for ctype in list(self.components):
                self._world._index_discard(ctype, self)
        self.components.clear()

    def __repr__(self) -> str:
        comp_names = ", ".join(c.__class__.__name__ for c in self.components.values())
        eid_part = f"{self.eid!r}, " if self.eid else ""
        return f"Entity({eid_part}id={self.id}, [{comp_names}])"


# ─── System ────────────────────────────────────────────

class System(ABC):
    """
    系统基类 — 处理拥有特定组件的实体。

    子类需要实现 ``update()`` 方法。
    可选实现 ``priority`` 类属性控制执行顺序（数值越小越先执行）。
    可选重写 ``enabled()`` 方法控制系统是否启用。

    用法：
        class MovementSystem(System):
            priority = 10  # 高优先级，先执行

            def update(self, world: World, dt: float) -> None:
                for entity in world.each(Position, Velocity):
                    pos = entity.get(Position)
                    vel = entity.get(Velocity)
                    pos.x += vel.dx * dt
    """

    # 类级属性说明：子类可定义 phase / priority / required_components
    priority: ClassVar[int] = 100
    #: 所属相位（``pre`` / ``update`` / ``post``），缺省 ``update``。
    #: ``pre`` 适合输入采样与时间推进，``post`` 适合表现层同步/清理。
    phase: ClassVar[str] = PHASE_UPDATE
    #: 声明"读哪些组件" / "写哪些组件"（**只用于冲突检测与告警，不用于并行调度**）。
    #: 不声明 = 不参与检查；声明了才能发现"两个系统同优先级写同一组件"这种隐性顺序依赖。
    reads: ClassVar[Tuple[Type["Component"], ...]] = ()
    writes: ClassVar[Tuple[Type["Component"], ...]] = ()

    @abstractmethod
    def update(self, world: "World", dt: float) -> None:
        """
        系统更新逻辑。由 World.update() 每帧调用。

        参数：
            world: 当前世界实例
            dt: 帧间隔时间（秒）
        """
        ...

    def enabled(self, world: "World") -> bool:
        """可选：控制系统是否启用。默认始终启用。"""
        return True


# ─── CommandBuffer ─────────────────────────────────────

class CommandBuffer:
    """结构变更队列：遍历期间要增删实体/组件时先排队，``World.update`` 末尾统一落地。

    为什么需要：``world.each(...)`` 是生成器，边遍历边 ``remove_entity`` 会让底层
    dict 变长/变短，直接抛 ``RuntimeError: dictionary changed size during iteration``。
    把变更排队，遍历期间容器不动，落地时再改。

    用法：
        for e in world.each(Health):
            if e.get(Health).hp <= 0:
                world.commands.remove_entity(e.id)

        ghost = world.commands.create("ghost")   # 先拿到游离实体，可以挂组件
        ghost.add(Health(10))                    # flush 时随实体一起入世界并建索引
    """

    __slots__ = ("_world", "_ops", "_flushing")

    def __init__(self, world: "World") -> None:
        self._world = world
        self._ops: List[tuple] = []
        self._flushing: bool = False

    def __len__(self) -> int:
        return len(self._ops)

    def __repr__(self) -> str:
        return f"CommandBuffer({len(self._ops)} pending)"

    def clear(self) -> None:
        self._ops.clear()

    def create(self, eid: Optional[str] = None) -> Entity:
        """排队创建实体；返回的实体在 flush 之前是游离的（不在世界、不建索引）。"""
        entity = Entity(eid)
        self._ops.append(("create", entity))
        return entity

    def remove_entity(self, key: str | int) -> None:
        """排队移除实体（eid 或 id）。"""
        self._ops.append(("remove", key))

    def add_component(self, entity: Entity, comp: Component) -> None:
        self._ops.append(("add", entity, comp))

    def remove_component(self, entity: Entity, comp_type: Type[Component]) -> None:
        self._ops.append(("rm", entity, comp_type))

    def flush(self) -> int:
        """按入队顺序落地，返回实际生效的条数。

        防重入：flush 期间若又产生新操作，留到下一次 flush（不会嵌套执行）。
        """
        if self._flushing or not self._ops:
            return 0
        self._flushing = True
        ops, self._ops = self._ops, []
        applied = 0
        try:
            for op in ops:
                kind = op[0]
                if kind == "create":
                    self._world.add_entity(op[1])
                    applied += 1
                elif kind == "remove":
                    if self._world.remove_entity(op[1]) is not None:
                        applied += 1
                elif kind == "add":
                    op[1].add(op[2])
                    applied += 1
                elif kind == "rm":
                    if op[1].remove(op[2]) is not None:
                        applied += 1
        finally:
            self._flushing = False
        return applied


# ─── World ─────────────────────────────────────────────

class World:
    """
    游戏世界 — 管理所有实体、系统和全局数据。

    核心功能：
        - 实体管理：增删查实体，按 eid 或 id 检索
        - 系统管理：按优先级排序执行
        - 组件查询：类型安全的实体过滤和遍历
        - 全局数据：跨系统的共享状态存储
        - 配置加载：从字典批量设置配置

    用法：
        world = World()
        player = world.create_entity("player")
        player.add(Position(5, 5)).add(Health(100))
        world.add_system(MovementSystem())
        world.update(0.016)
    """

    def __init__(self) -> None:
        # 实体存储：同时维护 eid->entity 和 id->entity 两套索引
        self.entities: Dict[str, Entity] = {}         # 按 eid 索引（主）
        self._entities_by_id: Dict[int, Entity] = {}  # 按 id 索引
        self.systems: List[System] = []
        self._systems_sorted: bool = True

        # 实例级自增实体 ID 计数器（替代原模块级全局计数器）
        self._next_entity_id: int = 0

        # 全局共享数据
        self._data: Dict[str, Any] = {}

        # 事件总线：系统内用 emit_deferred() 排队，World.update 在相位边界 flush
        self.events = EventBus()

        # 组件倒排索引：组件类型 -> {entity.id: Entity}。
        # 查询时先取"最小的那个桶"再逐个校验，避免每次都全表扫描（1 万实体 3 组件
        # 的 each() 从 O(n) 降到 O(k)）。索引由 Entity.add/remove 与 add_entity/
        # remove_entity 共同维护，绕过这些入口直接改 entity.components 会让索引失准。
        self._comp_index: Dict[Type[Component], Dict[int, Entity]] = {}

        # 结构变更队列：遍历期间要增删实体/组件时先排队，update 末尾统一落地
        self.commands = CommandBuffer(self)

        # ── flecs 风格：实体关系（带类型的边）+ 观察者 ──
        # 关系：subject 实体 id -> {relation_type: [object 实体 id, ...]}
        # （思路档 MIT；自研，不引入 C 库、不照搬 flecs 命名/结构）
        self._relations: Dict[int, Dict[str, List[int]]] = {}
        # 观察者：组件类型 -> {"added"/"removed": [callback(entity, ctype), ...]}
        self._observers: Dict[Type[Component], Dict[str, List[Callable]]] = {}
        # 防止观察者回调内再增删组件时递归触发的重入保护
        self._firing_observer: bool = False

    # ── 实体管理 ──────────────────────────────────────

    def create_entity(self, eid: Optional[str] = None) -> Entity:
        """快捷方法：创建实体并自动添加到世界中。

        参数：
            eid: 可选的字符串标识

        返回：
            新创建的 Entity 实例（已添加到世界）

        说明：
            实体 ID 由本 World 实例的 _next_entity_id 计数器分配，
            因此不同 World 的实体 ID 互不影响。
        """
        self._next_entity_id += 1
        entity = Entity(eid, entity_id=self._next_entity_id)
        return self.add_entity(entity)

    def add_entity(self, entity: Entity) -> Entity:
        """添加实体到世界。同名 eid 会被覆盖。返回实体支持链式调用。

        参数：
            entity: 要添加的实体

        返回：
            已添加的实体
        """
        if entity.eid:
            # 同名 eid 顶替：旧实体要一并摘掉（id 索引、组件索引、存活标记）
            old = self.entities.get(entity.eid)
            if old is not None and old.id != entity.id:
                self._entities_by_id.pop(old.id, None)
                self._detach(old)
            self.entities[entity.eid] = entity
        self._entities_by_id[entity.id] = entity
        entity._world = self
        entity._alive = True
        self._index_entity(entity)
        return entity

    def reset_id_counter(self, start: int = 0) -> None:
        """重置本 World 的实体 ID 计数器。

        用于测试隔离或需要确定性 ID 的场景。仅影响此 World 实例，
        不影响其他 World（这正是将计数器从模块全局移入实例的目的）。

        参数：
            start: 重置后的起始值（下一个实体 ID 将为 start + 1）
        """
        self._next_entity_id = start

    def get_entity(self, key: str | int) -> Optional[Entity]:
        """按 eid（字符串）或 id（整数）获取实体。

        参数：
            key: 实体的 eid 或 id

        返回：
            匹配的 Entity 或 None
        """
        if isinstance(key, str):
            return self.entities.get(key)
        return self._entities_by_id.get(key)

    def remove_entity(self, key: str | int) -> Optional[Entity]:
        """移除实体。支持 eid 字符串或 id 整数。

        参数：
            key: 实体的 eid 或 id

        返回：
            被移除的实体或 None
        """
        if isinstance(key, str):
            entity = self.entities.pop(key, None)
            if entity is not None:
                self._entities_by_id.pop(entity.id, None)
                self._detach(entity)
            return entity
        else:
            entity = self._entities_by_id.pop(key, None)
            if entity is not None and entity.eid is not None:
                self.entities.pop(entity.eid, None)
            if entity is not None:
                self._detach(entity)
            return entity

    # ── 实体关系（flecs 风格：带类型的边）──────────────
    # 自研实现「关系 = (subject, relation_type, object)」这一层概念；
    # 关系挂在 World 上（按实体 id 索引），不改动 Entity 的 __slots__ 与序列化契约。

    def add_relation(self, subject: str | int, relation_type: str, target: str | int) -> None:
        """建立一条带类型的关系边：subject --[relation_type]--> target。

        例：``world.add_relation("goblin", "child_of", "goblin_king")``。
        端点（subject / target）必须已存在于世界；重复同一条边被忽略。
        """
        subj = self.get_entity(subject)
        obj = self.get_entity(target)
        if subj is None or obj is None:
            raise KeyError("关系端点不存在于世界，无法建立关系")
        edges = self._relations.setdefault(subj.id, {}).setdefault(relation_type, [])
        if obj.id not in edges:
            edges.append(obj.id)

    def get_relations(self, subject: str | int, relation_type: str) -> List[int]:
        """返回 subject 在 ``relation_type`` 下指向的所有 object 实体 id。"""
        subj = self.get_entity(subject)
        if subj is None:
            return []
        return list(self._relations.get(subj.id, {}).get(relation_type, []))

    def relations_of(self, subject: str | int) -> Dict[str, List[int]]:
        """返回 subject 的全部关系（relation_type -> [object id, ...]）的副本。"""
        subj = self.get_entity(subject)
        if subj is None:
            return {}
        return {k: list(v) for k, v in self._relations.get(subj.id, {}).items()}

    def relates_to(self, subject: str | int, relation_type: str, target: str | int) -> bool:
        """判断 subject 是否通过 ``relation_type`` 指向 target。"""
        subj = self.get_entity(subject)
        obj = self.get_entity(target)
        if subj is None or obj is None:
            return False
        return obj.id in self._relations.get(subj.id, {}).get(relation_type, [])

    def remove_relation(self, subject: str | int, relation_type: str, target: str | int) -> bool:
        """移除一条关系边；成功返回 True。"""
        subj = self.get_entity(subject)
        if subj is None:
            return False
        edges = self._relations.get(subj.id, {}).get(relation_type)
        if edges is None:
            return False
        obj = self.get_entity(target)
        oid = obj.id if obj is not None else target
        if oid in edges:
            edges.remove(oid)
            if not edges:
                del self._relations[subj.id][relation_type]
            return True
        return False

    # ── 观察者（flecs 风格：组件增删触发回调）──────────
    # 自研实现「observer = 对组件集的增/删做出反应的系统」这一层概念。

    def add_observer(
        self,
        component_type: Type[Component],
        event: str,
        callback: Callable[[Entity, Type[Component]], None],
    ) -> None:
        """注册观察者：当 ``component_type`` 被 ``event``（"added"/"removed"）时调用。

        ``callback(entity, component_type)``。
        """
        if event not in ("added", "removed"):
            raise ValueError(f"未知 observer 事件: {event!r}（仅 added/removed）")
        self._observers.setdefault(component_type, {}).setdefault(event, []).append(callback)

    def remove_observer(
        self,
        component_type: Type[Component],
        event: str,
        callback: Callable[[Entity, Type[Component]], None],
    ) -> bool:
        """注销观察者；成功返回 True。"""
        cbs = self._observers.get(component_type, {}).get(event)
        if cbs is None:
            return False
        if callback in cbs:
            cbs.remove(callback)
            return True
        return False

    def has_observer(self, component_type: Type[Component], event: str) -> bool:
        """是否存在针对该组件类型与事件类型的观察者。"""
        return bool(self._observers.get(component_type, {}).get(event))

    # ── 组件索引（内部） ──────────────────────────────

    def _index_add(self, ctype: Type[Component], entity: Entity) -> None:
        bucket = self._comp_index.get(ctype)
        if bucket is None:
            bucket = self._comp_index[ctype] = {}
        bucket[entity.id] = entity
        # flecs 风格 observer：组件被加入时触发（重入保护，避免回调内再增删组件时嵌套触发）
        self._fire_observers(entity, ctype, "added")

    def _index_discard(self, ctype: Type[Component], entity: Entity) -> None:
        bucket = self._comp_index.get(ctype)
        if bucket is not None:
            bucket.pop(entity.id, None)
        # flecs 风格 observer：组件被移除时触发
        self._fire_observers(entity, ctype, "removed")

    def _fire_observers(self, entity: Entity, ctype: Type[Component], event: str) -> None:
        """触发某组件类型上注册的 observer 回调（added / removed）。"""
        if self._firing_observer:
            return
        cbs = self._observers.get(ctype, {}).get(event)
        if not cbs:
            return
        self._firing_observer = True
        try:
            for cb in list(cbs):
                cb(entity, ctype)
        finally:
            self._firing_observer = False

    def _index_entity(self, entity: Entity) -> None:
        for ctype in entity.components:
            self._index_add(ctype, entity)

    def _detach(self, entity: Entity) -> Entity:
        """把实体从索引上摘掉并标记失效（代际 +1，旧句柄可据此识别）。"""
        for ctype in list(entity.components):
            self._index_discard(ctype, entity)
        entity._alive = False
        entity._generation += 1
        entity._world = None
        return entity

    def _candidates(self, comp_types: Sequence[Type[Component]]) -> Dict[int, Entity]:
        """返回最小的候选桶；任一类型无实体时返回空桶。"""
        if not comp_types:
            return self._entities_by_id
        buckets = []
        for t in comp_types:
            b = self._comp_index.get(t)
            if not b:
                return {}
            buckets.append(b)
        return min(buckets, key=len)

    def entity_count(self) -> int:
        """当前实体总数。"""
        return len(self._entities_by_id)

    def each_entity(self) -> Iterator[Entity]:
        """遍历所有实体。"""
        yield from self._entities_by_id.values()

    def list_entity_ids(self) -> list[str]:
        """列出所有实体的 eid（字符串键）。"""
        return list(self.entities.keys())

    def has_entity(self, eid: str) -> bool:
        """检查指定 eid 的实体是否存在。"""
        return eid in self.entities

    def entity_ids(self) -> Iterator[str]:
        """遍历所有实体 eid。"""
        yield from self.entities.keys()

    # ── 系统管理 ──────────────────────────────────────

    def add_system(self, system: System, *, warn_conflicts: bool = True) -> "World":
        """添加系统，标记需要重新排序。返回 self 支持链式调用。

        ``warn_conflicts=True`` 时，若新系统与已注册系统**同相位、同 priority**
        且读写集合重叠，会发一条 ``RuntimeWarning``——这是"隐性顺序依赖"，
        不声明就发现不了。不想看告警就显式传 ``False``。

        用法：
            world.add_system(MovementSystem()).add_system(RenderSystem())
        """
        phase = getattr(system, "phase", PHASE_UPDATE)
        if phase not in PHASE_ORDER:
            raise ValueError(f"未知系统相位 {phase!r}；可选 {PHASE_ORDER}")
        if warn_conflicts:
            for c in self._conflicts_with(system):
                warnings.warn(
                    f"{type(system).__name__} 与 {c['other']} 同相位({c['phase']})、"
                    f"同 priority({c['priority']}) 且 {c['reason']}："
                    f"{', '.join(c['components'])}；请显式调整 priority 或 phase",
                    RuntimeWarning, stacklevel=2)
        self.systems.append(system)
        self._systems_sorted = False
        return self

    def _conflicts_with(self, system: System) -> List[dict]:
        """一个系统与已注册系统之间的读写冲突（同相位 + 同 priority）。"""
        out: List[dict] = []
        phase = getattr(system, "phase", PHASE_UPDATE)
        w_new = set(getattr(system, "writes", ()) or ())
        r_new = set(getattr(system, "reads", ()) or ())
        if not (w_new or r_new):
            return out
        for other in self.systems:
            if getattr(other, "phase", PHASE_UPDATE) != phase:
                continue
            if other.priority != system.priority:
                continue
            w_old = set(getattr(other, "writes", ()) or ())
            r_old = set(getattr(other, "reads", ()) or ())
            reason = None
            hit = set()
            if w_new & w_old:
                reason = "都写"
                hit = w_new & w_old
            elif w_new & r_old:
                reason = "一个写、另一个读"
                hit = w_new & r_old
            elif r_new & w_old:
                reason = "一个读、另一个写"
                hit = r_new & w_old
            if reason:
                out.append({"other": type(other).__name__, "phase": phase,
                            "priority": system.priority, "reason": reason,
                            "components": sorted(c.__name__ for c in hit)})
        return out

    def check_conflicts(self) -> List[dict]:
        """全量检查：返回所有"同相位 + 同 priority + 读写重叠"的系统对。

        这是**告警**不是错误：Python 单线程下系统仍按注册顺序执行，
        只是这个顺序是隐式的，改代码时容易踩。CI 里可以断言它为空。
        """
        out: List[dict] = []
        for i, s in enumerate(self.systems):
            for other in self.systems[i + 1:]:
                if getattr(other, "phase", PHASE_UPDATE) != getattr(s, "phase", PHASE_UPDATE):
                    continue
                if other.priority != s.priority:
                    continue
                w1 = set(getattr(s, "writes", ()) or ())
                r1 = set(getattr(s, "reads", ()) or ())
                w2 = set(getattr(other, "writes", ()) or ())
                r2 = set(getattr(other, "reads", ()) or ())
                reason, hit = None, set()
                if w1 & w2:
                    reason, hit = "都写", w1 & w2
                elif w1 & r2:
                    reason, hit = "一个写、另一个读", w1 & r2
                elif r1 & w2:
                    reason, hit = "一个读、另一个写", r1 & w2
                if reason:
                    out.append({"a": type(s).__name__, "b": type(other).__name__,
                                "phase": getattr(s, "phase", PHASE_UPDATE),
                                "priority": s.priority, "reason": reason,
                                "components": sorted(c.__name__ for c in hit)})
        return out

    def get_system(self, system_type: Type[T]) -> Optional[T]:
        """按类型获取系统。

        用法：
            movement = world.get_system(MovementSystem)
        """
        for s in self.systems:
            if isinstance(s, system_type):
                return s  # type: ignore[return-value]
        return None

    def remove_system(self, system_type: Type[System]) -> None:
        """按类型移除系统。"""
        self.systems = [s for s in self.systems if not isinstance(s, system_type)]
        self._systems_sorted = False

    def has_system(self, system_type: Type[System]) -> bool:
        """检查是否存在指定类型的系统。"""
        return any(isinstance(s, system_type) for s in self.systems)

    def _ensure_systems_sorted(self) -> None:
        """延迟排序：仅在需要时才按优先级排序系统列表。"""
        if not self._systems_sorted:
            # 先相位、后 priority；同键保持插入顺序（sort 是稳定的）
            self.systems.sort(key=lambda s: (PHASE_ORDER.index(getattr(s, "phase", PHASE_UPDATE)),
                                             s.priority))
            self._systems_sorted = True

    # ── 组件查询 ──────────────────────────────────────

    def get_entities_with_components(self, *comp_types: Type[Component]) -> List[Entity]:
        """返回同时拥有所有指定组件的实体列表。

        用法：
            # 获取所有有位置且可交互的实体
            entities = world.get_entities_with_components(Position, Interactable)
        """
        if not comp_types:
            return list(self._entities_by_id.values())
        cand = self._candidates(comp_types)
        return [e for e in cand.values() if e.has_all(*comp_types)]

    # 别名，兼容 pywallpaper 风格命名
    find_entities_with = get_entities_with_components

    def get_first_with_components(self, *comp_types: Type[Component]) -> Optional[Entity]:
        """返回第一个匹配所有组件的实体，或 None。"""
        if not comp_types:
            return next(iter(self._entities_by_id.values()), None)
        cand = self._candidates(comp_types)
        for entity in cand.values():
            if entity.has_all(*comp_types):
                return entity
        return None

    def get_entities_with_any(self, *comp_types: Type[Component]) -> List[Entity]:
        """返回拥有任意一个指定组件的实体列表。"""
        result: List[Entity] = []
        for entity in self._entities_by_id.values():
            if entity.has_any(*comp_types):
                result.append(entity)
        return result

    def each(self, *comp_types: Type[Component]) -> Iterator[Entity]:
        """生成器：遍历所有拥有指定组件的实体。

        用法：
            for entity in world.each(Position, Health):
                pos = entity.get(Position)
                hp = entity.get(Health)
                ...
        """
        if not comp_types:
            yield from self._entities_by_id.values()
            return
        cand = self._candidates(comp_types)
        for entity in cand.values():
            if entity.has_all(*comp_types):
                yield entity

    def each_any(self, *comp_types: Type[Component]) -> Iterator[Entity]:
        """生成器：遍历拥有任意一个指定组件的实体。"""
        for entity in self._entities_by_id.values():
            if entity.has_any(*comp_types):
                yield entity

    # ── 全局数据共享 ──────────────────────────────────

    def set_data(self, key: str, value: Any) -> None:
        """存储全局共享数据。

        用法：
            world.set_data("current_level", 3)
            world.set_data("player_name", "Alice")
        """
        self._data[key] = value

    def get_data(self, key: str, default: Any = None) -> Any:
        """读取全局共享数据。

        参数：
            key: 数据键名
            default: 键不存在时返回的默认值

        返回：
            存储的数据值
        """
        return self._data.get(key, default)

    def has_data(self, key: str) -> bool:
        """检查是否存在指定的共享数据键。"""
        return key in self._data

    def clear_data(self) -> None:
        """清除所有全局共享数据。"""
        self._data.clear()

    # ── 配置加载 ──────────────────────────────────────

    def load_config(self, config: Dict[str, Any]) -> None:
        """从字典批量加载配置，存入全局数据。

        用法：
            world.load_config({"cell_size": 20, "tilemap": "map_01"})
        """
        self._data.update(config)

    # ── 世界更新 ──────────────────────────────────────

    def update(self, dt: float) -> None:
        """按优先级顺序更新所有启用的系统。

        参数：
            dt: 帧间隔时间（秒）
        """
        self._ensure_systems_sorted()
        for phase in PHASE_ORDER:
            for system in self.systems:
                if getattr(system, "phase", PHASE_UPDATE) != phase:
                    continue
                if system.enabled(self):
                    system.update(self, dt)
            # 相位边界：结构变更在这里统一落地（遍历期间不改容器，就没有
            # "dict changed size during iteration"），延迟事件也在这里派发。
            # 于是 post 系统能看到 update 阶段的增删，而 update 阶段的系统
            # 不会在遍历中途被自己 emit 的回调打断。
            self.commands.flush()
            self.events.flush_deferred()

    def flush_commands(self) -> int:
        """手动落地 ``commands`` 里排队的结构变更（返回生效条数）。

        ``update()`` 会自动调用；只有在不跑 update 的批处理/工具场景才需要手动调。
        """
        return self.commands.flush()

    # ── 调试辅助 ──────────────────────────────────────

    def debug_print(self) -> None:
        """打印世界状态（调试用）。"""
        print(f"[World] {self.entity_count()} entities, {len(self.systems)} systems")
        if self._data:
            print(f"  Data keys: {list(self._data.keys())}")
        for entity in self._entities_by_id.values():
            print(f"  {entity}")
        for s in self.systems:
            status = "ON" if s.enabled(self) else "OFF"
            print(f"  [{status}] {s.__class__.__name__} (priority={s.priority})")

    def reset(self) -> None:
        """重置世界：清除所有实体、系统和数据。

        注意：仅清除内部状态，本 World 的实体 ID 计数器不会重置。
        """
        for entity in list(self._entities_by_id.values()):
            self._detach(entity)
        self.entities.clear()
        self._entities_by_id.clear()
        self._comp_index.clear()
        self.commands.clear()
        self.systems.clear()
        self._systems_sorted = True
        self._data.clear()
        self._relations.clear()
        self._observers.clear()
        self._firing_observer = False
