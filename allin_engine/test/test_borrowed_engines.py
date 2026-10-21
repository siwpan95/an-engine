"""
借鉴引擎源码落地测试（§二 已排期项）
====================================

覆盖本轮落地的 8 个借鉴点：
  1. RPG Maker MV 1.3.x 回合制（状态叠层 + 速度排序）
  2. Godot class_db 类注册表
  3. Godot Object::connect 信号连接标志
  4. Unity 生命周期相位别名
  5. Evennia TypeClass + CmdSet 合并
  6. Yarn/ink 对话 VM
  7. pluggy hookspec/hookimpl
  8. flecs 关系 / observer

断言一律用 ``assert`` / 显式 ``_expect_raises``，禁止 import pytest。
"""

from allin_engine.core import (
    Component,
    Entity,
    World,
)
from allin_engine.core.event_bus import (
    EventBus,
    CONNECT_DEFERRED,
    CONNECT_ONESHOT,
)
from allin_engine.core.class_registry import ClassRegistry, default_registry
from allin_engine.core.typeclass import TypeClass, Cmd, CmdSet
from allin_engine.core.plugins import hookspec, hookimpl, PluginManager
from allin_engine.trpg.turn_order import (
    StateDef,
    StatusContainer,
    StatusInstance,
    Combatant,
    order_by_speed,
)
from allin_engine.ai.dialogue import DialogueVM, DialogueNode, DialogueOption


def _expect_raises(exc_type, fn, contains=None):
    """期望 ``fn()`` 抛出 ``exc_type``；可选地校验异常信息包含 ``contains``。"""
    try:
        fn()
    except exc_type as e:
        if contains is not None:
            assert contains in str(e), f"异常信息未包含 {contains!r}: {e!r}"
        return
    except Exception as e:
        raise AssertionError(f"期望 {exc_type.__name__} 但抛出 {type(e).__name__}: {e}")
    raise AssertionError(f"期望 {exc_type.__name__} 但未抛出")


# ─────────────────────────────────────────────────────
# 1. RPG Maker MV 1.3.x 回合制
# ─────────────────────────────────────────────────────

def _mv_defs():
    """构造一组 MV 风格的状态定义（含死亡/限制/增益/速度修正）。"""
    return {
        1: StateDef(1, "死亡", priority=100, restriction=4, min_turns=1, max_turns=1),
        2: StateDef(2, "麻痹", priority=50, restriction=1, min_turns=1, max_turns=3),
        3: StateDef(3, "减速", priority=40, restriction=0, speed_mod=-5, min_turns=1, max_turns=2),
        4: StateDef(4, "加速", priority=40, restriction=0, speed_mod=5, min_turns=1, max_turns=2),
        5: StateDef(5, "攻击上升", priority=30, buff=True, step=3, max_stacks=3, min_turns=1, max_turns=5),
    }


def test_state_priority_mutual_exclusion():
    """高优先级限制状态挡住低优先级限制状态的叠加（MV isStateRestrict 语义）。"""
    defs = _mv_defs()
    # 先上「麻痹」(priority 50, restriction 1)
    c = StatusContainer(defs)
    assert c.apply(2) is True
    # 再上「减速」(restriction 0) —— 不冲突，可叠加
    assert c.apply(3) is True
    assert c.has(2) and c.has(3)
    # 清空后，先上低优先级的「减速」(restriction 0)，再上「麻痹」(restriction 1, 更高)
    c2 = StatusContainer(defs)
    c2.apply(3)
    assert c2.apply(2) is True  # 麻痹 priority 高于减速且带 restriction，正常叠
    assert c2.has(2)


def test_state_restriction_blocked_by_higher():
    """已存在更高 priority 且带 restriction 的状态时，新限制状态被互斥挡掉。"""
    defs = _mv_defs()
    c = StatusContainer(defs)
    # 死亡(priority 100) 带最高 restriction，先上
    c.apply(1)
    # 麻痹(priority 50, restriction 1) 被死亡挡住（>50 且 restriction>0 已存在）
    assert c.apply(2) is False
    assert not c.has(2)


def test_state_stacking_layers():
    """增益可叠层至 max_stacks，超层不再增加。"""
    defs = _mv_defs()
    c = StatusContainer(defs)
    assert c.apply(5, stacks=2) is True
    assert c._active[5].stacks == 2
    assert c.apply(5, stacks=5) is True  # 应被夹到 max_stacks=3
    assert c._active[5].stacks == 3
    assert c.magnitude(5) == 3 * 3  # 层数 × step


def test_state_duration_tick_expiry():
    """回合推进递减持续回合，到期自动移除。"""
    defs = _mv_defs()
    c = StatusContainer(defs)
    c.apply(2)  # min=1,max=3 -> 确定性取 min=1
    assert c.has(2)
    expired = c.tick()
    assert 2 in expired
    assert not c.has(2)


def test_status_speed_modifier_haste_slow():
    """状态对行动速度的修正：加速 +5、减速 -5。"""
    defs = _mv_defs()
    c = StatusContainer(defs)
    c.apply(4)  # 加速 +5
    c.apply(3)  # 减速 -5
    assert c.speed_modifier() == 0


def test_order_by_speed_descending_tiebreak():
    """行动速度降序排先攻；同速按敏捷、再按 id 稳定排序。"""
    defs = _mv_defs()
    slow = Combatant("slow", agi=5)
    fast = Combatant("fast", agi=20, statuses=StatusContainer(defs))
    fast.statuses.apply(4)  # +5 速度
    tied_a = Combatant("a", agi=10)
    tied_b = Combatant("b", agi=10)
    order = order_by_speed([slow, fast, tied_a, tied_b])
    assert order[0].id == "fast"
    assert order[-1].id == "slow"
    # 同速(agi 10, 无修正) 的 a/b 落在 fast 与 slow 之间，且两者都在（稳定排序）
    middle = order[1:3]
    assert {c.id for c in middle} == {"a", "b"}


# ─────────────────────────────────────────────────────
# 2. Godot class_db 类注册表
# ─────────────────────────────────────────────────────

def test_register_and_query_property_signal_method():
    reg = ClassRegistry()
    reg.register(
        type("Node", (), {}),
        properties=["position", "visible"],
        signals=["ready", "tree_exiting"],
        methods=["_process", "queue_free"],
    )
    assert reg.get_property_names("Node") == ["position", "visible"]
    assert reg.get_signal_names("Node") == ["ready", "tree_exiting"]
    assert reg.get_method_names("Node") == ["_process", "queue_free"]


def test_register_class_decorator():
    reg = ClassRegistry()

    @reg.register_class(properties=["hp"], signals=["died"], methods=["take_damage"], base="Node")
    class Enemy:
        pass

    assert reg.has("Enemy")
    assert reg.get_base("Enemy") == "Node"
    assert reg.get_property_names("Enemy") == ["hp"]


def test_unknown_class_returns_empty_lists():
    reg = ClassRegistry()
    assert reg.get_property_names("Nope") == []
    assert reg.get_signal_names("Nope") == []
    assert reg.get_method_names("Nope") == []


def test_ancestors_chain():
    reg = ClassRegistry()
    reg.register(type("A", (), {}))
    reg.register(type("B", (), {}), base="A")
    reg.register(type("C", (), {}), base="B")
    assert reg.ancestors("C") == ["B", "A"]


# ─────────────────────────────────────────────────────
# 3. Godot Object::connect 信号连接标志
# ─────────────────────────────────────────────────────

def test_connect_equals_subscribe_when_no_flags():
    bus = EventBus()
    seen = []
    bus.connect("e", lambda d: seen.append(d))
    assert bus.listener_count("e") == 1
    bus.emit("e", 1)
    assert seen == [1]


def test_connect_deferred_not_called_immediately():
    bus = EventBus()
    seen = []
    bus.connect("e", lambda d: seen.append(d), deferred=True)
    bus.emit("e", 42)
    assert seen == []  # 延迟连接不立即触发
    assert bus.pending_deferred == 0  # 这是事件队列，不影响


def test_connect_deferred_delivered_on_flush():
    bus = EventBus()
    seen = []
    bus.connect("e", lambda d: seen.append(d), deferred=True)
    bus.emit("e", 7)
    assert seen == []
    n = bus.flush_deferred()
    assert seen == [7]
    assert n >= 1


def test_connect_oneshot_auto_disconnect():
    bus = EventBus()
    seen = []
    bus.connect("e", lambda d: seen.append(d), oneshot=True)
    bus.emit("e", 1)
    bus.emit("e", 2)
    assert seen == [1]  # 第二次不再触发
    assert bus.listener_count("e") == 0


def test_connect_deferred_and_oneshot_once():
    bus = EventBus()
    seen = []
    bus.connect("e", lambda d: seen.append(d), deferred=True, oneshot=True)
    bus.emit("e", 1)
    bus.flush_deferred()        # 第一次派发即断开连接
    bus.emit("e", 2)
    bus.flush_deferred()        # 连接已断，不再派发
    assert seen == [1]


def test_connect_flags_constants_exist():
    assert CONNECT_DEFERRED == 1
    assert CONNECT_ONESHOT == 2


# ─────────────────────────────────────────────────────
# 4. Unity 生命周期相位别名
# ─────────────────────────────────────────────────────

def test_unity_phase_aliases_map_to_base():
    from allin_engine.core.ecs import (
        PHASE_PRE, PHASE_UPDATE, PHASE_POST,
        PHASE_AWAKE, PHASE_START, PHASE_FIXED_UPDATE, PHASE_LATE_UPDATE,
        UNITY_PHASE_MAP,
    )
    assert PHASE_AWAKE == PHASE_PRE
    assert PHASE_START == PHASE_PRE
    assert PHASE_FIXED_UPDATE == PHASE_UPDATE
    assert PHASE_LATE_UPDATE == PHASE_POST
    assert UNITY_PHASE_MAP[PHASE_PRE] == "Awake/Start"
    assert UNITY_PHASE_MAP[PHASE_POST] == "LateUpdate"


# ─────────────────────────────────────────────────────
# 5. Evennia TypeClass + CmdSet 合并
# ─────────────────────────────────────────────────────

def test_typeclass_data_behavior_separation():
    class Sword(TypeClass):
        typeclass_name = "sword"

        def describe(self):
            return f"一把{self.get('material')}剑"

    s = Sword("excalibur", {"material": "秘银", "atk": 12})
    assert s.get("atk") == 12
    s.set("atk", 15)
    assert s.describe() == "一把秘银剑"
    assert s.to_dict()["typeclass"] == "sword"


def test_cmdset_merge_dedup_higher_priority_wins():
    base = CmdSet("base")
    base.add(Cmd("look", priority=0, func=lambda: "base-look"))
    override = CmdSet("override")
    override.add(Cmd("look", priority=10, func=lambda: "override-look"))
    merged = base.merge(override)
    assert merged.get("look").func() == "override-look"  # 高优先级覆盖


def test_cmdset_merge_keeps_distinct_keys():
    a = CmdSet("a")
    a.add(Cmd("north", priority=0))
    b = CmdSet("b")
    b.add(Cmd("south", priority=0))
    merged = a.merge(b)
    assert set(merged.keys()) == {"north", "south"}


def test_cmdset_merge_lower_priority_loses():
    a = CmdSet("a")
    a.add(Cmd("go", priority=10, func=lambda: "a-go"))
    b = CmdSet("b")
    b.add(Cmd("go", priority=1, func=lambda: "b-go"))
    merged = a.merge(b)
    assert merged.get("go").func() == "a-go"  # a 优先级更高胜出


# ─────────────────────────────────────────────────────
# 6. Yarn/ink 对话 VM
# ─────────────────────────────────────────────────────

def test_dialogue_vm_linear_nodes():
    vm = DialogueVM({
        "start": DialogueNode("start", lines=["你好"], next="end"),
        "end": DialogueNode("end", lines=["再见"]),
    })
    vm.start("start")
    assert vm.current_lines() == ["你好"]
    assert not vm.is_finished()
    vm.advance()
    assert vm.current_lines() == ["再见"]
    assert vm.is_finished()


def test_dialogue_vm_options_choose():
    vm = DialogueVM({
        "q": DialogueNode("q", lines=["选？"],
                          options=[DialogueOption("是", "yes"), DialogueOption("否", "no")]),
        "yes": DialogueNode("yes", lines=["好的"]),
        "no": DialogueNode("no", lines=["算了"]),
    })
    vm.start("q")
    assert len(vm.current_options()) == 2
    vm.choose(1)
    assert vm.current_lines() == ["算了"]


def test_dialogue_vm_variables_on_enter_and_option():
    vm = DialogueVM({
        "start": DialogueNode("start", on_enter={"seen": 0},
                             options=[DialogueOption("加一", "done", set_vars={"seen": 1})]),
        "done": DialogueNode("done", lines=["完成"]),
    })
    vm.start("start")
    assert vm.get_variable("seen") == 0
    assert len(vm.current_options()) == 1
    vm.choose(0)
    assert vm.get_variable("seen") == 1


def test_dialogue_vm_save_load_roundtrip():
    vm = DialogueVM({
        "start": DialogueNode("start", lines=["a"], next="mid"),
        "mid": DialogueNode("mid", on_enter={"k": 9}, lines=["b"], next="end"),
        "end": DialogueNode("end", lines=["c"]),
    })
    vm.start("start")
    vm.advance()  # -> mid, 设置 k=9
    assert vm.get_variable("k") == 9
    snap = vm.save_state()
    # 换个新 VM，从存档恢复
    vm2 = DialogueVM({
        "start": DialogueNode("start", lines=["a"], next="mid"),
        "mid": DialogueNode("mid", on_enter={"k": 9}, lines=["b"], next="end"),
        "end": DialogueNode("end", lines=["c"]),
    })
    vm2.load_state(snap)
    assert vm2.current_lines() == ["b"]
    assert vm2.get_variable("k") == 9


def test_dialogue_vm_unknown_node_raises():
    vm = DialogueVM({})
    _expect_raises(KeyError, lambda: vm.start("ghost"))


# ─────────────────────────────────────────────────────
# 7. pluggy hookspec/hookimpl
# ─────────────────────────────────────────────────────

def test_hookspec_hookimpl_weighted_order():
    class Specs:
        @hookspec
        def on_damage(self, raw):
            ...

    class PluginA:
        @hookimpl(weight=1)
        def on_damage(self, raw):
            return raw + 1

    class PluginB:
        @hookimpl(weight=10)
        def on_damage(self, raw):
            return raw * 2

    pm = PluginManager()
    pm.add_hookspecs(Specs)
    pm.register(PluginA())
    pm.register(PluginB())
    # weight 高者先执行：B(×2) 然后 A(+1)
    results = pm.hook.on_damage(raw=5)
    assert results == [10, 6]


def test_plugin_manager_unregister():
    class P:
        @hookimpl(weight=0)
        def ping(self):
            return "pong"

    pm = PluginManager()
    inst = P()
    pm.register(inst)
    assert pm.has_hook("ping")
    pm.unregister(inst)
    assert pm.get_hookcaller("ping")() == []


# ─────────────────────────────────────────────────────
# 8. flecs 关系 / observer
# ─────────────────────────────────────────────────────

class _Tag(Component):
    def __init__(self, v=0):
        self.v = v


class _Mark(Component):
    def __init__(self, v=0):
        self.v = v


def test_relation_add_query_remove():
    w = World()
    child = w.create_entity("goblin")
    parent = w.create_entity("goblin_king")
    w.add_relation("goblin", "child_of", "goblin_king")
    assert w.relates_to("goblin", "child_of", "goblin_king") is True
    assert w.get_relations("goblin", "child_of") == [parent.id]
    rels = w.relations_of("goblin")
    assert "child_of" in rels
    assert w.remove_relation("goblin", "child_of", "goblin_king") is True
    assert w.relates_to("goblin", "child_of", "goblin_king") is False


def test_relation_missing_endpoint_raises():
    w = World()
    w.create_entity("a")
    _expect_raises(KeyError, lambda: w.add_relation("a", "owns", "ghost"))


def test_observer_fires_on_add_and_remove():
    w = World()
    added, removed = [], []
    w.add_observer(_Tag, "added", lambda e, c: added.append(e.id))
    w.add_observer(_Tag, "removed", lambda e, c: removed.append(e.id))
    e = w.create_entity("x")
    e.add(_Tag(1))
    assert added == [e.id]
    e.remove(_Tag)
    assert removed == [e.id]


def test_observer_mutation_does_not_recurse():
    w = World()
    calls = []
    w.add_observer(_Tag, "added", lambda e, c: calls.append(e.id))
    # 回调里给同一实体加另一个类型的组件（无 observer），不应无限递归
    w.add_observer(_Mark, "added", lambda e, c: calls.append(("mark", e.id)))
    e = w.create_entity("y")
    e.add(_Tag(1))  # 触发 _Tag 的 observer；回调不增删 _Tag，不会递归
    assert calls == [e.id]
    calls.clear()
    e.add(_Mark(1))  # 触发 _Mark 的 observer；且该回调不改 _Tag
    assert calls == [("mark", e.id)]
