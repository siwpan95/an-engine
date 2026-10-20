"""系统相位 + 延迟事件：顺序与重入的机械判据。

相位是"比 priority 更硬"的顺序：pre 一定在 update 前，update 一定在 post 前。
延迟事件的价值不在"晚一点"，而在**相位边界**——系统遍历自己触发的回调时，
容器不会被改，重入不会打断遍历。
"""

import pytest

from allin_engine.core import Component, System, World
from allin_engine.core.ecs import PHASE_POST, PHASE_PRE, PHASE_UPDATE
from allin_engine.core.event_bus import EventBus


class Marker(Component):
    def __init__(self, tag: str = ""):
        self.tag = tag


def _recorder(log, name):
    class _Rec(System):
        def update(self, world, dt):
            log.append(name)

    return _Rec


# ─── 相位顺序 ───────────────────────────────────────

def test_phase_order_beats_priority():
    log = []
    Pre = _recorder(log, "pre"); Pre.phase = PHASE_PRE; Pre.priority = 999
    Upd = _recorder(log, "update"); Upd.phase = PHASE_UPDATE; Upd.priority = 500
    Post = _recorder(log, "post"); Post.phase = PHASE_POST; Post.priority = 1

    w = World()
    # 故意按乱序注册
    w.add_system(Post()).add_system(Upd()).add_system(Pre())
    w.update(0.016)
    assert log == ["pre", "update", "post"], log


def test_priority_only_orders_within_phase():
    log = []
    A = _recorder(log, "u10"); A.priority = 10
    B = _recorder(log, "u1"); B.priority = 1
    C = _recorder(log, "u99"); C.priority = 99
    w = World()
    w.add_system(A()).add_system(C()).add_system(B())
    w.update(0.016)
    assert log == ["u1", "u10", "u99"], log


def test_default_phase_is_update():
    class S(System):
        def update(self, world, dt):
            pass

    assert S.phase == PHASE_UPDATE
    assert System.phase == PHASE_UPDATE


def test_unknown_phase_rejected_on_add():
    class Bad(System):
        phase = "render"

        def update(self, world, dt):
            pass

    w = World()
    with pytest.raises(ValueError):
        w.add_system(Bad())


def test_disabled_system_skipped_in_any_phase():
    log = []

    class Off(System):
        phase = PHASE_PRE
        priority = 1

        def update(self, world, dt):
            log.append("off")

        def enabled(self, world):
            return False

    w = World()
    w.add_system(Off())
    w.update(0.016)
    assert log == []


# ─── 相位边界：结构变更落地 ─────────────────────────

def test_commands_flushed_between_phases():
    seen = {}

    class Spawner(System):
        phase = PHASE_PRE

        def update(self, world, dt):
            world.commands.create("spawned").add(Marker("p"))

    class Checker(System):
        phase = PHASE_UPDATE

        def update(self, world, dt):
            seen["found"] = world.get_entity("spawned") is not None
            seen["has_marker"] = (world.get_entity("spawned") is not None
                                  and world.get_entity("spawned").has(Marker))

    w = World()
    w.add_system(Checker()).add_system(Spawner())
    assert w.get_entity("spawned") is None
    w.update(0.016)
    assert seen == {"found": True, "has_marker": True}


def test_same_phase_commands_still_deferred_to_phase_end():
    seen = {}

    class Spawner(System):
        priority = 1

        def update(self, world, dt):
            world.commands.create("late").add(Marker())

    class Checker(System):
        priority = 2

        def update(self, world, dt):
            seen["visible"] = world.get_entity("late") is not None

    w = World()
    w.add_system(Spawner()).add_system(Checker())
    w.update(0.016)
    assert seen["visible"] is False, "同相位内不该立刻可见（否则遍历容器会在中途变长）"
    assert w.get_entity("late") is not None, "相位结束后必须落地"


# ─── 延迟事件 ───────────────────────────────────────

def test_deferred_event_not_delivered_synchronously():
    log = []

    class Pre1(System):
        phase = PHASE_PRE

        def update(self, world, dt):
            world.events.emit_deferred("ping", 1)
            log.append("after_emit")

    w = World()
    w.events.subscribe("ping", lambda data: log.append(f"ping{data}"))
    w.add_system(Pre1())
    w.update(0.016)
    assert log == ["after_emit", "ping1"], log


def test_deferred_event_visible_in_next_phase():
    log = []

    class PreEmit(System):
        phase = PHASE_PRE

        def update(self, world, dt):
            world.events.emit_deferred("tick", 1)

    class UpdCheck(System):
        phase = PHASE_UPDATE

        def update(self, world, dt):
            log.append(f"update sees {world.events.pending_deferred} pending")

    w = World()
    w.events.subscribe("tick", lambda data: log.append("tick"))
    w.add_system(PreEmit()).add_system(UpdCheck())
    w.update(0.016)
    assert log == ["tick", "update sees 0 pending"], log


def test_flush_deferred_returns_notification_count():
    bus = EventBus()
    got = []
    bus.subscribe("a", got.append)
    bus.subscribe("a", got.append)
    bus.emit_deferred("a", 1)
    bus.emit_deferred("a", 2)
    assert bus.pending_deferred == 2
    assert bus.flush_deferred() == 4          # 2 事件 × 2 监听器
    assert got == [1, 1, 2, 2]
    assert bus.pending_deferred == 0


def test_events_queued_during_flush_wait_for_next_round():
    bus = EventBus()
    seen = []

    def on_a(_):
        seen.append("a")
        bus.emit_deferred("b", None)          # flush 期间入队 → 下一轮

    bus.subscribe("a", on_a)
    bus.subscribe("b", lambda _: seen.append("b"))
    bus.emit_deferred("a", None)
    bus.flush_deferred()
    assert seen == ["a"], seen
    assert bus.pending_deferred == 1
    bus.flush_deferred()
    assert seen == ["a", "b"]


def test_clear_deferred():
    bus = EventBus()
    bus.emit_deferred("x")
    bus.emit_deferred("y")
    assert bus.clear_deferred() == 2
    assert bus.pending_deferred == 0
    assert bus.flush_deferred() == 0


def test_clear_all_drops_pending():
    bus = EventBus()
    bus.subscribe("x", lambda _: None)
    bus.emit_deferred("x")
    bus.clear()
    assert bus.pending_deferred == 0


def test_world_has_event_bus():
    w = World()
    assert isinstance(w.events, EventBus)
    assert w.events.pending_deferred == 0


def test_sync_emit_still_immediate():
    w = World()
    seen = []
    w.events.subscribe("now", lambda d: seen.append(d))
    w.events.emit("now", 7)
    assert seen == [7]
    assert w.events.pending_deferred == 0
