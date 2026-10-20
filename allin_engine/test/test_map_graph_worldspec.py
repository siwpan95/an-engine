"""MapGraph 读 worldspec：三仓契约的玩法侧入口。

这里刻意**不 import worldbuilder**——消费方只认文件，不认生成方的代码。
测试用合成目录（meta.json + graph.json + pois.json），把"读得对、走得通、
坏数据不炸"三件事钉死。
"""

import json
import tempfile
from pathlib import Path


from allin_engine.world.map_graph import MapGraph, MapNode, WORLDSPEC_VERSION


def _expect_raises(exc_type, fn, contains=None):
    """pytest.raises 的等价物（本仓测试栈不依赖 pytest）。"""
    try:
        fn()
    except exc_type as exc:
        if contains is not None and contains not in str(exc):
            raise AssertionError(f"异常消息不含 {contains!r}，实际为：{exc}") from None
        return exc
    raise AssertionError(f"预期抛出 {exc_type.__name__}，但没有抛出")


def _dir(tmp_path=None) -> Path:
    """runner 直接调用测试函数（不注入 fixture），所以这里要能自己建临时目录。"""
    if tmp_path is None:
        return Path(tempfile.mkdtemp(prefix="ws_graph_"))
    return Path(tmp_path)


def _write_spec(tmp_path, *, nodes, edges, spec=WORLDSPEC_VERSION, tile_m=2.0,
                with_graph=True, with_pois=False):
    (tmp_path / "meta.json").write_text(json.dumps({
        "spec": spec, "generator": "test", "seed": 1,
        "size": [64, 64], "tile_m": tile_m,
        "up_axis": "Y", "handedness": "right", "sea_level": 0.3,
    }, ensure_ascii=False), encoding="utf-8")
    if with_graph:
        (tmp_path / "graph.json").write_text(json.dumps({
            "spec": spec,
            "nodes": nodes,
            "edges": edges,
        }, ensure_ascii=False), encoding="utf-8")
    if with_pois:
        (tmp_path / "pois.json").write_text(json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [n["x"], n["z"]]},
                "properties": {"id": n["id"], "kind": n.get("kind", ""),
                               "name": n.get("name", ""), "score": n.get("score", 0.0),
                               "meta": n.get("meta") or {}},
            } for n in nodes],
        }, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def _n(nid, x, z, kind="village", name=""):
    return {"id": nid, "kind": kind, "x": x, "z": z, "name": name or nid,
            "score": 1.0, "meta": {"elevation": 0.4}}


def _e(a, b, length, kind="trunk", points=None):
    return {"a": a, "b": b, "kind": kind, "length": length,
            "straight": length, "cost": length,
            "points": points or [[0, 0], [1, 1]]}


def test_load_nodes_edges_and_metadata(tmp_path=None):
    tmp_path = _dir(tmp_path)
    spec = _write_spec(
        tmp_path,
        nodes=[_n("town-00", 10, 20, "town"), _n("village-00", 30, 40)],
        edges=[_e("town-00", "village-00", 7.5)],
    )
    g = MapGraph.from_worldspec(spec)
    assert len(g.nodes) == 2
    assert set(g.nodes) == {"town-00", "village-00"}
    assert g.nodes["town-00"].metadata["kind"] == "town"
    assert g.nodes["town-00"].metadata["elevation"] == 0.4
    assert g.nodes["town-00"].metadata["tile_m"] == 2.0
    # 双向：两侧都要连通且都能查到边
    assert g.nodes["town-00"].is_connected_to("village-00")
    assert g.nodes["village-00"].is_connected_to("town-00")
    assert g.edge_length("town-00", "village-00") == 7.5
    assert g.edge_length("village-00", "town-00") == 7.5
    assert g.load_report["skipped_edges"] == []


def test_route_prefers_short_weight_not_hop_count(tmp_path=None):
    tmp_path = _dir(tmp_path)
    # 直连 10，经中间点 3+3=6 —— Dijkstra 必须选后者
    spec = _write_spec(
        tmp_path,
        nodes=[_n("a", 0, 0), _n("b", 1, 1), _n("c", 2, 2)],
        edges=[_e("a", "c", 10.0), _e("a", "b", 3.0), _e("b", "c", 3.0)],
    )
    g = MapGraph.from_worldspec(spec)
    assert g.route("a", "c") == ["a", "b", "c"]
    assert g.route("a", "c", weighted=False) in (["a", "c"], ["a", "b", "c"])
    assert g.route_length(["a", "b", "c"]) == 6.0


def test_route_unknown_nodes_returns_none(tmp_path=None):
    tmp_path = _dir(tmp_path)
    spec = _write_spec(tmp_path, nodes=[_n("a", 0, 0)], edges=[])
    g = MapGraph.from_worldspec(spec)
    assert g.route("a", "ghost") is None
    assert g.route("ghost", "a") is None
    assert g.route("a", "a") == ["a"]


def test_route_avoids_locked_intermediate(tmp_path=None):
    tmp_path = _dir(tmp_path)
    spec = _write_spec(
        tmp_path,
        nodes=[_n("a", 0, 0), _n("b", 1, 1), _n("c", 2, 2)],
        edges=[_e("a", "c", 10.0), _e("a", "b", 3.0), _e("b", "c", 3.0)],
    )
    g = MapGraph.from_worldspec(spec)
    g.lock_node("b")
    assert g.route("a", "c", ignore_locks=False) == ["a", "c"]
    assert g.route("a", "c", ignore_locks=True) == ["a", "b", "c"]


def test_pois_only_fallback_has_no_edges(tmp_path=None):
    tmp_path = _dir(tmp_path)
    nodes = [_n("town-00", 5, 5, "town"), _n("mine-00", 9, 9, "mine")]
    spec = _write_spec(tmp_path, nodes=nodes, edges=[], with_graph=False,
                       with_pois=True)
    g = MapGraph.from_worldspec(spec)
    assert len(g.nodes) == 2
    assert g.edges == {}
    assert g.route("town-00", "mine-00") is None
    assert g.load_report["has_edges"] is False


def test_dangling_edge_skipped_by_default_and_strict_raises(tmp_path=None):
    tmp_path = _dir(tmp_path)
    spec = _write_spec(
        tmp_path,
        nodes=[_n("a", 0, 0), _n("b", 1, 1)],
        edges=[_e("a", "b", 2.0), _e("a", "ghost-99", 2.0)],
    )
    g = MapGraph.from_worldspec(spec)
    assert len(g.load_report["skipped_edges"]) == 1
    assert g.load_report["skipped_edges"][0]["b"] == "ghost-99"

    _expect_raises(ValueError, lambda: MapGraph.from_worldspec(spec, strict=True))


def test_spec_version_mismatch_raises(tmp_path=None):
    tmp_path = _dir(tmp_path)
    spec = _write_spec(tmp_path, nodes=[_n("a", 0, 0)], edges=[],
                       spec="worldspec/99")
    _expect_raises(ValueError, lambda: MapGraph.from_worldspec(spec))


def test_missing_meta_raises(tmp_path=None):
    tmp_path = _dir(tmp_path)
    _expect_raises(FileNotFoundError, lambda: MapGraph.from_worldspec(tmp_path))


def test_nearest_and_world_pos(tmp_path=None):
    tmp_path = _dir(tmp_path)
    spec = _write_spec(
        tmp_path,
        nodes=[_n("town-00", 10, 10, "town"), _n("mine-00", 50, 50, "mine")],
        edges=[_e("town-00", "mine-00", 5.0)],
        tile_m=4.0,
    )
    g = MapGraph.from_worldspec(spec)
    assert g.nearest(12, 12) == "town-00"
    assert g.nearest(48, 49) == "mine-00"
    assert g.nearest(48, 49, kinds=("town",)) == "town-00"
    assert g.world_pos("town-00") == (10.0, 10.0)
    assert g.world_pos("town-00", meters=True) == (40.0, 40.0)
    assert g.world_pos("ghost") is None


def test_edges_survive_serialization(tmp_path=None):
    tmp_path = _dir(tmp_path)
    spec = _write_spec(
        tmp_path,
        nodes=[_n("a", 0, 0), _n("b", 1, 1)],
        edges=[_e("a", "b", 2.5, points=[[0, 0], [0.5, 0.5], [1, 1]])],
    )
    g = MapGraph.from_worldspec(spec)
    back = MapGraph.from_dict(g.to_dict())
    assert back.edge_length("a", "b") == 2.5
    assert back.edge_info("b", "a")["points"][-1] == [0, 0]      # 反向折线也翻了
    assert back.nodes["a"].connections == g.nodes["a"].connections


def test_remove_node_cleans_edge_tables(tmp_path=None):
    tmp_path = _dir(tmp_path)
    spec = _write_spec(
        tmp_path,
        nodes=[_n("a", 0, 0), _n("b", 1, 1)],
        edges=[_e("a", "b", 2.0)],
    )
    g = MapGraph.from_worldspec(spec)
    assert g.remove_node("b") is True
    assert "b" not in g.edges.get("a", {})
    assert g.nodes["a"].connections == []
    assert g.edge_length("a", "b") == 1.0                        # 缺省权重，不抛


def test_manual_add_edge_rejects_unknown_endpoint():
    g = MapGraph()
    g.add_node(MapNode("a"))
    _expect_raises(KeyError, lambda: g.add_edge("a", "ghost", length=1.0))
    _expect_raises(ValueError, lambda: g.add_edge("a", "a", length=1.0))
