"""ECS 存储 v2 测试：组件倒排索引 / 实体代际 / 结构变更队列。

对应方案里的 P0-1（存储）与 P0-2（变更缓冲）。判据分三类：
  1. **语义不变**：索引只是加速，查询结果必须与"全表扫描"逐一对齐；
  2. **索引不失准**：增删改、同名顶替、clear、reset 之后都不能留脏数据；
  3. **确实更快**：稀组件查询要有量级收益（否则这层复杂度白付）。
"""

import time

from allin_engine.core import Component, System, World
from allin_engine.core.ecs import CommandBuffer, Entity


class Pos(Component):
    def __init__(self, x=0.0, y=0.0):
        self.x = x
        self.y = y


class Vel(Component):
    def __init__(self, dx=0.0, dy=0.0):
        self.dx = dx
        self.dy = dy


class Rare(Component):
    def __init__(self, tag="r"):
        self.tag = tag


def _linear(world, *types):
    """旧实现的等价物：全表扫描。用来对拍索引结果。"""
    return [e for e in world._entities_by_id.values() if e.has_all(*types)]


def _ids(entities):
    return {e.id for e in entities}


# ── 语义：索引与全表扫描必须一致 ──────────────────────

def test_query_matches_linear_scan():
    w = World()
    for i in range(200):
        e = w.create_entity(f"e{i}")
        if i % 2 == 0:
            e.add(Pos(i, i))
        if i % 3 == 0:
            e.add(Vel(1, 1))
        if i % 17 == 0:
            e.add(Rare())
    assert _ids(w.get_entities_with_components(Pos)) == _ids(_linear(w, Pos))
    assert _ids(w.get_entities_with_components(Pos, Vel)) == _ids(_linear(w, Pos, Vel))
    assert _ids(w.get_entities_with_components(Rare, Pos)) == _ids(_linear(w, Rare, Pos))
    assert _ids(w.each(Pos, Vel)) == _ids(_linear(w, Pos, Vel))


def test_empty_types_yield_everything():
    w = World()
    a = w.create_entity("a")
    b = w.create_entity("b")
    assert _ids(w.get_entities_with_components()) == {a.id, b.id}
    assert _ids(w.each()) == {a.id, b.id}
    assert w.get_first_with_components() is not None


def test_first_match_and_absent_type():
    w = World()
    w.create_entity("a").add(Pos())
    assert w.get_first_with_components(Pos).eid == "a"
    assert w.get_first_with_components(Rare) is None
    assert w.get_entities_with_components(Rare) == []


# ── 索引一致性 ────────────────────────────────────────

def test_index_updates_on_component_add_remove():
    w = World()
    e = w.create_entity("a")
    e.add(Pos(1, 1))
    assert w.get_entities_with_components(Pos) == [e]
    e.remove(Pos)
    assert w.get_entities_with_components(Pos) == []
    assert w._comp_index[Pos] == {}


def test_clear_components_deindexes():
    w = World()
    e = w.create_entity("a").add(Pos()).add(Vel())
    e.clear_components()
    assert w.get_entities_with_components(Pos) == []
    assert w.get_entities_with_components(Vel) == []
    assert e.components == {}


def test_remove_entity_by_eid_and_id():
    w = World()
    a = w.create_entity("a").add(Pos())
    b = w.create_entity("b").add(Pos())
    w.remove_entity("a")
    assert w.get_entities_with_components(Pos) == [b]
    w.remove_entity(b.id)
    assert w.get_entities_with_components(Pos) == []
    assert w._comp_index[Pos] == {}


def test_same_eid_replaces_and_detaches_old():
    w = World()
    old = w.create_entity("boss").add(Pos(9, 9))
    new = w.create_entity("boss").add(Pos(1, 1))
    assert not old.is_alive, "被同名 eid 顶替的实体应失效"
    assert new.is_alive
    assert _ids(w.get_entities_with_components(Pos)) == {new.id}
    assert w.get_entity("boss") is new


def test_add_entity_with_prebuilt_components_indexes_them():
    w = World()
    e = Entity("pre")                      # 游离实体：先挂组件，再入世界
    e.add(Pos(1, 2)).add(Vel())
    assert w._comp_index == {}, "游离实体的组件不该进索引"
    w.add_entity(e)
    assert e in w.get_entities_with_components(Pos, Vel)


def test_reset_clears_index_and_detaches():
    w = World()
    a = w.create_entity("a").add(Pos())
    w.reset()
    assert w.entity_count() == 0
    assert w._comp_index == {}
    assert not a.is_alive


# ── 代际 ──────────────────────────────────────────────

def test_generation_increments_on_removal():
    w = World()
    e = w.create_entity("a")
    assert e.generation == 0 and e.is_alive
    w.remove_entity("a")
    assert e.generation == 1 and not e.is_alive
    assert w.get_entity("a") is None


def test_stale_handle_absent_from_queries():
    w = World()
    e = w.create_entity("a").add(Pos())
    w.remove_entity("a")
    assert e not in w.get_entities_with_components(Pos)
    assert e not in list(w.each(Pos))


# ── 结构变更队列 ──────────────────────────────────────

def test_command_buffer_create_with_components():
    w = World()
    ghost = w.commands.create("ghost")
    ghost.add(Pos(5, 5))                     # 游离期间不建索引
    assert w.get_entity("ghost") is None
    assert w._comp_index == {}
    assert w.commands.flush() == 1
    assert w.get_entity("ghost") is ghost
    assert ghost in w.get_entities_with_components(Pos)


def test_command_buffer_remove_and_component_ops():
    w = World()
    a = w.create_entity("a").add(Pos())
    b = w.create_entity("b").add(Pos())
    w.commands.remove_entity("a")
    w.commands.add_component(b, Vel())
    w.commands.remove_component(b, Pos)
    assert len(w.commands) == 3
    assert w.flush_commands() == 3
    assert w.get_entity("a") is None
    assert b.get(Vel) is not None and b.get(Pos) is None
    assert w.get_entities_with_components(Pos) == []


def test_removal_during_iteration_does_not_break():
    w = World()
    for i in range(50):
        w.create_entity(f"e{i}").add(Pos(i, 0))
    seen = 0
    for e in w.each(Pos):
        seen += 1
        if e.get(Pos).x % 2 == 0:
            w.commands.remove_entity(e.id)
    assert seen == 50, "遍历中排队删除不应影响本轮遍历"
    assert w.entity_count() == 50, "flush 之前实体还在"
    assert w.commands.flush() == 25
    assert w.entity_count() == 25


def test_update_flushes_pending_commands():
    w = World()

    class Spawner(System):
        priority = 10

        def update(self, world, dt):
            world.commands.create(f"spawn_{int(dt * 1000)}").add(Pos())
            for e in world.each(Pos):
                if e.eid and e.eid.startswith("dead"):
                    world.commands.remove_entity(e.eid)

    w.create_entity("dead_1").add(Pos())
    w.add_system(Spawner())
    w.update(0.016)
    assert w.get_entity("dead_1") is None, "update 末尾应自动落地删除"
    assert w.get_entity("spawn_16") is not None, "update 末尾应自动落地创建"
    assert len(w.commands) == 0


def test_ops_queued_after_flush_wait_for_next_round():
    """flush 只处理"本轮快照"；落地过程中新入队的操作留到下一轮。"""
    w = World()
    w.commands.create("outer").add(Pos())
    assert w.commands.flush() == 1
    assert w.get_entity("outer") is not None

    w.commands.create("inner").add(Pos())
    assert w.get_entity("inner") is None, "新入队的还没落地"
    assert w.commands.flush() == 1
    assert w.get_entity("inner") is not None


def test_command_buffer_clear():
    w = World()
    w.commands.create("x")
    assert len(w.commands) == 1
    w.commands.clear()
    assert len(w.commands) == 0
    assert w.commands.flush() == 0


# ── 性能：稀组件查询要有量级收益 ──────────────────────

def test_rare_component_query_is_fast():
    w = World()
    n = 20000
    for i in range(n):
        e = w.create_entity(f"e{i}")
        e.add(Pos(float(i), 0.0))
        if i % 100 == 0:
            e.add(Rare())          # 1%
    t0 = time.perf_counter()
    got = w.get_entities_with_components(Pos, Rare)
    t_index = time.perf_counter() - t0
    assert len(got) == n // 100

    t0 = time.perf_counter()
    ref = _linear(w, Pos, Rare)
    t_linear = time.perf_counter() - t0
    assert len(ref) == len(got)

    # 索引走 1% 的桶；全表要扫 100%。给足余量，避免 CI 抖动误报。
    assert t_index < t_linear / 3.0, (
        f"索引没有带来量级收益：index={t_index*1000:.2f}ms linear={t_linear*1000:.2f}ms"
    )
    assert t_index < 0.02, f"20k 实体稀组件查询 {t_index*1000:.2f}ms，超出预算"


def test_each_over_large_world_under_budget():
    w = World()
    for i in range(20000):
        w.create_entity(f"e{i}").add(Pos(float(i), 0.0)).add(Vel(1.0, 0.0))
    t0 = time.perf_counter()
    n = sum(1 for _ in w.each(Pos, Vel))
    dt = time.perf_counter() - t0
    assert n == 20000
    assert dt < 0.05, f"20k 实体 each() 耗时 {dt*1000:.1f}ms，超出预算"


def test_command_buffer_repr_and_len():
    w = World()
    cb = CommandBuffer(w)
    assert len(cb) == 0 and "0 pending" in repr(cb)
