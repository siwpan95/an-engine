"""系统读写声明与冲突告警：把"隐式执行顺序"变成可检查的东西。

Python 单线程下系统按注册顺序跑，两个系统同相位、同 priority 又都写同一组件时，
谁先谁后完全取决于谁先 `add_system`——这是最容易在重构时踩的坑。
`reads/writes` 声明 + `check_conflicts()` 就是把它显式化。
"""

import warnings

from allin_engine.core import Component, System, World
from allin_engine.core.ecs import PHASE_PRE


class Pos(Component):
    def __init__(self, x: float = 0.0):
        self.x = x


class Vel(Component):
    def __init__(self, dx: float = 0.0):
        self.dx = dx


def _sys(name, *, writes=(), reads=(), priority=100, phase="update"):
    # update 必须写进类字典——ABC 在类创建时就算好了 __abstractmethods__，
    # 先建类再 cls.update = ... 是不管用的（实例化仍报 abstract）。
    def _noop(self, world, dt):
        pass

    cls = type(name, (System,), {"writes": tuple(writes), "reads": tuple(reads),
                                 "priority": priority, "phase": phase,
                                 "update": _noop})
    return cls()


def test_write_write_same_priority_conflicts():
    w = World()
    w.add_system(_sys("A", writes=(Pos,)), warn_conflicts=False)
    w.add_system(_sys("B", writes=(Pos,)), warn_conflicts=False)
    c = w.check_conflicts()
    assert len(c) == 1
    assert {c[0]["a"], c[0]["b"]} == {"A", "B"}
    assert c[0]["reason"] == "都写"
    assert c[0]["components"] == ["Pos"]


def test_different_priority_is_not_conflict():
    w = World()
    w.add_system(_sys("A", writes=(Pos,), priority=10), warn_conflicts=False)
    w.add_system(_sys("B", writes=(Pos,), priority=20), warn_conflicts=False)
    assert w.check_conflicts() == []


def test_different_phase_is_not_conflict():
    w = World()
    w.add_system(_sys("A", writes=(Pos,), phase=PHASE_PRE), warn_conflicts=False)
    w.add_system(_sys("B", writes=(Pos,), phase="update"), warn_conflicts=False)
    assert w.check_conflicts() == []


def test_read_write_same_priority_conflicts():
    w = World()
    w.add_system(_sys("Writer", writes=(Pos,)), warn_conflicts=False)
    w.add_system(_sys("Reader", reads=(Pos,)), warn_conflicts=False)
    c = w.check_conflicts()
    assert len(c) == 1
    # 先注册的 Writer 写、后注册的 Reader 读 → 报"一个写、另一个读"
    assert c[0]["reason"] == "一个写、另一个读"


def test_no_declarations_never_conflicts():
    w = World()
    w.add_system(_sys("A"), warn_conflicts=False)
    w.add_system(_sys("B"), warn_conflicts=False)
    assert w.check_conflicts() == []


def test_add_system_emits_runtime_warning():
    w = World()
    w.add_system(_sys("A", writes=(Pos,)), warn_conflicts=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        w.add_system(_sys("B", writes=(Pos,)))
    assert caught, "同相位同优先级写同一组件时应告警"
    assert issubclass(caught[0].category, RuntimeWarning)
    assert "Pos" in str(caught[0].message)


def test_warn_conflicts_false_is_silent():
    w = World()
    w.add_system(_sys("A", writes=(Pos,)), warn_conflicts=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        w.add_system(_sys("B", writes=(Pos,)), warn_conflicts=False)
    assert caught == []


def test_conflict_reports_overlapping_components_only():
    w = World()
    w.add_system(_sys("A", writes=(Pos, Vel)), warn_conflicts=False)
    w.add_system(_sys("B", writes=(Vel,)), warn_conflicts=False)
    c = w.check_conflicts()
    assert len(c) == 1
    assert c[0]["components"] == ["Vel"], "只报重叠的那个组件"


def test_multiple_pairs_reported():
    w = World()
    for name in ("A", "B", "C"):
        w.add_system(_sys(name, writes=(Pos,)), warn_conflicts=False)
    # 三对两两冲突
    assert len(w.check_conflicts()) == 3


def test_declared_systems_still_run_in_order():
    log = []

    class A(System):
        writes = (Pos,)
        priority = 100

        def update(self, world, dt):
            log.append("A")

    class B(System):
        writes = (Pos,)
        priority = 100

        def update(self, world, dt):
            log.append("B")

    w = World()
    w.add_system(A(), warn_conflicts=False)
    w.add_system(B(), warn_conflicts=False)
    w.update(0.016)
    assert log == ["A", "B"], "告警只提示隐性顺序，不改变既有执行顺序"
