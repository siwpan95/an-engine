"""
地图节点图 — 章节/区域间的导航图结构。

用于表示游戏世界中的地点连接关系，支持锁定/解锁、访问追踪和路径查询。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

#: worldspec 的版本串（与 worldbuilder 侧严格一致；不匹配直接拒读）
WORLDSPEC_VERSION = "worldspec/1"


@dataclass
class MapNode:
    """地图上的一个节点（位置/区域）。

    属性:
        node_id: 节点唯一标识
        name: 显示名称
        description: 节点描述
        chapter: 解锁所需章节
        is_locked: 是否锁定
        connections: 连接的 node_id 列表
        visited: 是否已访问
        metadata: 扩展元数据
    """

    node_id: str
    name: str = ""
    description: str = ""
    chapter: str = ""
    is_locked: bool = False
    connections: list[str] = field(default_factory=list)
    visited: bool = False
    metadata: dict = field(default_factory=dict)

    def connect_to(self, other_id: str) -> None:
        """添加一条到另一节点的连接。"""
        if other_id not in self.connections:
            self.connections.append(other_id)

    def disconnect_from(self, other_id: str) -> bool:
        """移除一条到另一节点的连接。"""
        try:
            self.connections.remove(other_id)
            return True
        except ValueError:
            return False

    def is_connected_to(self, other_id: str) -> bool:
        """检查是否连接到另一节点。"""
        return other_id in self.connections

    def unlock(self) -> None:
        """解锁节点。"""
        self.is_locked = False

    def lock(self) -> None:
        """锁定节点。"""
        self.is_locked = True

    def visit(self) -> None:
        """标记为已访问。"""
        self.visited = True

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "node_id": self.node_id,
            "name": self.name,
            "description": self.description,
            "chapter": self.chapter,
            "is_locked": self.is_locked,
            "connections": self.connections,
            "visited": self.visited,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MapNode":
        """从字典反序列化。"""
        return cls(
            node_id=data["node_id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            chapter=data.get("chapter", ""),
            is_locked=data.get("is_locked", False),
            connections=data.get("connections", []),
            visited=data.get("visited", False),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        locked = "[锁定]" if self.is_locked else ""
        visited_mark = "[已访问]" if self.visited else ""
        return f"MapNode({self.node_id}{locked}{visited_mark})"


# ============================================================
# MapGraph
# ============================================================

@dataclass
class MapGraph:
    """地图有向图 — 管理节点间的导航与解锁。

    用法:
        graph = MapGraph()
        graph.add_node(MapNode("hub", "大厅", connections=["room_a"]))
        graph.add_node(MapNode("room_a", "房间A", connections=["hub"]))
        ok, reason = graph.can_move_to("room_a")
        if ok:
            graph.move_to("room_a")
    """

    nodes: dict[str, MapNode] = field(default_factory=dict)
    current_node: str | None = None
    #: 边权与几何：``edges[a][b] = {"length", "kind", "points", ...}``。
    #: 用嵌套 dict 而不是 (a,b) 元组做键，是为了能直接 JSON 序列化。
    edges: dict[str, dict[str, dict]] = field(default_factory=dict)
    #: 从 worldspec 载入时的体检信息（跳过的悬空边、tile_m 等），不参与序列化
    load_report: dict = field(default_factory=dict, repr=False)

    # ================================================================
    # 节点管理
    # ================================================================

    def add_node(self, node: MapNode) -> None:
        """添加一个节点。首个添加的节点自动设为当前位置。"""
        self.nodes[node.node_id] = node
        if self.current_node is None:
            self.current_node = node.node_id

    def remove_node(self, node_id: str) -> bool:
        """移除一个节点。同时清理其他节点到该节点的连接。"""
        if node_id not in self.nodes:
            return False
        del self.nodes[node_id]
        # 清理残留引用（邻接表 + 边权表）
        for n in self.nodes.values():
            if node_id in n.connections:
                n.connections.remove(node_id)
        self.edges.pop(node_id, None)
        for targets in self.edges.values():
            targets.pop(node_id, None)
        if self.current_node == node_id:
            self.current_node = None
        return True

    def get_node(self, node_id: str) -> MapNode | None:
        """获取指定节点。"""
        return self.nodes.get(node_id)

    # ================================================================
    # 边（带权重与几何）
    # ================================================================

    def add_edge(self, a: str, b: str, *, length: Optional[float] = None,
                 kind: str = "", points: Optional[list] = None,
                 bidirectional: bool = True, **extra: Any) -> None:
        """加一条边（默认双向），同时维护 ``node.connections``。

        ``length`` 缺省 1.0；``points`` 是 ``[[x, z], ...]`` 折线（worldspec 的
        ``graph.json`` 直接给这个形状），``kind`` 用来区分 trunk/loop/spur。
        """
        if a not in self.nodes or b not in self.nodes:
            raise KeyError(f"端点不在图中：a={a!r} b={b!r}")
        if a == b:
            raise ValueError("不允许自环")
        info: dict = {"kind": kind, "length": float(length) if length is not None else 1.0}
        if points:
            info["points"] = [list(pt) for pt in points]
        info.update(extra)
        self.edges.setdefault(a, {})[b] = info
        self.nodes[a].connect_to(b)
        if bidirectional:
            rev = dict(info)
            if points:
                rev["points"] = [list(pt) for pt in reversed(points)]
            self.edges.setdefault(b, {})[a] = rev
            self.nodes[b].connect_to(a)

    def edge_info(self, a: str, b: str) -> Optional[dict]:
        """取 ``a → b`` 的边信息；不存在返回 ``None``。"""
        return (self.edges.get(a) or {}).get(b)

    def edge_length(self, a: str, b: str) -> float:
        """边权（缺省 1.0，保证未配权重的图仍能寻路）。"""
        info = self.edge_info(a, b)
        return float(info["length"]) if info else 1.0

    # ================================================================
    # worldspec 接入
    # ================================================================

    @classmethod
    def from_worldspec(cls, spec_dir, *, strict: bool = False) -> "MapGraph":
        """从 worldspec 目录建图（worldbuilder 的产物，**不 import 它**）。

        - 优先读 ``graph.json``（含路网与过河点）；没有则退回 ``pois.json``
          （只有节点、没有边，适合"还没修路"的世界）。
        - 节点 ``metadata`` 里带 ``x`` / ``z``（格坐标）、``kind``、``elevation``、``tile_m``。
        - ``strict=True`` 时悬空边抛 ``ValueError``；默认跳过并记进 ``load_report``。
          （玩法层不该因为一条坏边整张图废掉，但 CI 里应该严格。）
        """
        d = Path(spec_dir)
        meta_p = d / "meta.json"
        if not meta_p.exists():
            raise FileNotFoundError(f"{meta_p} 不存在：这不是一个 worldspec 目录")
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        if meta.get("spec") != WORLDSPEC_VERSION:
            raise ValueError(f"spec 版本不匹配：期望 {WORLDSPEC_VERSION}，"
                             f"收到 {meta.get('spec')!r}")

        tile = float(meta.get("tile_m", 1.0))
        graph = cls()
        graph.load_report = {"spec": meta["spec"], "source": str(d),
                             "tile_m": tile, "size": list(meta.get("size") or []),
                             "skipped_edges": [], "has_edges": False}

        rows: list[dict] = []
        edges: list[dict] = []
        gp = d / "graph.json"
        pp = d / "pois.json"
        if gp.exists():
            g = json.loads(gp.read_text(encoding="utf-8"))
            rows = list(g.get("nodes") or [])
            edges = list(g.get("edges") or [])
            graph.load_report["has_edges"] = bool(edges)
        elif pp.exists():
            geo = json.loads(pp.read_text(encoding="utf-8"))
            for f in geo.get("features", []):
                props = f.get("properties") or {}
                x, z = (f.get("geometry") or {}).get("coordinates", [0, 0])[:2]
                rows.append({"id": props.get("id"), "kind": props.get("kind", ""),
                             "name": props.get("name", ""), "x": x, "z": z,
                             "score": props.get("score", 0.0),
                             "meta": props.get("meta") or {}})
        elif strict:
            raise FileNotFoundError(f"{d} 里既没有 graph.json 也没有 pois.json")

        for row in rows:
            if not row.get("id"):
                continue
            extra_meta = dict(row.get("meta") or {})
            metadata = {"x": float(row.get("x", 0.0)), "z": float(row.get("z", 0.0)),
                        "kind": row.get("kind", ""), "tile_m": tile,
                        "score": float(row.get("score", 0.0))}
            metadata.update({k: extra_meta[k] for k in ("elevation", "biome", "slope")
                             if k in extra_meta})
            graph.add_node(MapNode(node_id=str(row["id"]),
                                   name=str(row.get("name", "")),
                                   metadata=metadata))

        for e in edges:
            a, b = e.get("a"), e.get("b")
            if a not in graph.nodes or b not in graph.nodes:
                if strict:
                    raise ValueError(f"graph.json 的边指向未知节点：{a!r} -> {b!r}")
                graph.load_report["skipped_edges"].append({"a": a, "b": b})
                continue
            graph.add_edge(str(a), str(b), length=e.get("length"),
                           kind=e.get("kind", ""), points=e.get("points"),
                           cost=e.get("cost"))

        graph.load_report["nodes"] = len(graph.nodes)
        graph.load_report["edges"] = sum(len(v) for v in graph.edges.values()) // 2
        return graph

    # ================================================================
    # 查询
    # ================================================================

    def world_pos(self, node_id: str, *, meters: bool = False) -> Optional[tuple[float, float]]:
        """节点坐标 ``(x, z)``；``meters=True`` 时乘 ``tile_m`` 换成米。"""
        node = self.nodes.get(node_id)
        if node is None or "x" not in node.metadata:
            return None
        scale = float(node.metadata.get("tile_m", 1.0)) if meters else 1.0
        return (float(node.metadata["x"]) * scale, float(node.metadata["z"]) * scale)

    def nearest(self, x: float, z: float, *,
                kinds: Optional[Iterable[str]] = None) -> Optional[str]:
        """离 ``(x, z)`` 最近的节点 id；``kinds`` 可限定类型（``("town","port")``）。"""
        allow = set(kinds) if kinds is not None else None
        best_id: Optional[str] = None
        best_d = float("inf")
        for nid, node in self.nodes.items():
            if allow is not None and node.metadata.get("kind") not in allow:
                continue
            if "x" not in node.metadata:
                continue
            d = (float(node.metadata["x"]) - x) ** 2 + (float(node.metadata["z"]) - z) ** 2
            if d < best_d:
                best_d, best_id = d, nid
        return best_id

    def route(self, start: str, goal: str, *, weighted: bool = True,
              ignore_locks: bool = True) -> Optional[list[str]]:
        """最短路。``weighted=True`` 走 Dijkstra（边权 = 路长），否则 BFS。

        未知节点返回 ``None``（不抛异常——玩法层经常拿"可能不存在的目标"来问）。
        """
        if start not in self.nodes or goal not in self.nodes:
            return None
        if start == goal:
            return [start]
        # 延迟导入：pathfinding 在模块层 import 了本模块，这里反向导入会成环
        from allin_engine.world.pathfinding import GraphPathFinder

        pf = GraphPathFinder(self, ignore_locks=ignore_locks)
        if not weighted:
            return pf.bfs(start, goal)
        return pf.dijkstra(start, goal, weight_fn=self.edge_length)

    def route_length(self, path: Optional[Iterable[str]]) -> float:
        """一条路线的总长（格）。"""
        if not path:
            return 0.0
        seq = list(path)
        return sum(self.edge_length(a, b) for a, b in zip(seq, seq[1:]))

    # ================================================================
    # 导航
    # ================================================================

    def get_current(self) -> Optional[MapNode]:
        """获取当前节点。"""
        if self.current_node:
            return self.nodes.get(self.current_node)
        return None

    def set_current(self, node_id: str) -> bool:
        """直接设置当前节点（不检查可达性）。"""
        if node_id in self.nodes:
            self.current_node = node_id
            return True
        return False

    def can_move_to(self, target_id: str) -> tuple[bool, str]:
        """检查是否可移动到目标节点。

        返回 (can_move, reason).
        """
        current = self.get_current()
        if not current:
            return (False, "没有当前位置")
        target = self.nodes.get(target_id)
        if not target:
            return (False, f"未知地点: {target_id}")
        if target.is_locked:
            return (False, f"{target.name} 尚未解锁")
        if target_id not in current.connections:
            return (False, f"无法从 {current.name} 到达 {target.name}")
        return (True, "")

    def move_to(self, target_id: str) -> bool:
        """移动到目标节点。成功返回 True。"""
        can_move, _ = self.can_move_to(target_id)
        if not can_move:
            return False
        old = self.get_current()
        if old:
            old.visit()
        self.current_node = target_id
        target = self.nodes[target_id]
        target.visit()
        return True

    def get_available_destinations(self) -> list[MapNode]:
        """获取当前节点可达的所有目标节点（排除锁定的）。"""
        current = self.get_current()
        if not current:
            return []
        result: list[MapNode] = []
        for nid in current.connections:
            node = self.nodes.get(nid)
            if node and not node.is_locked:
                result.append(node)
        return result

    def get_all_destinations(self) -> list[MapNode]:
        """获取当前节点的所有连接节点（含锁定的）。"""
        current = self.get_current()
        if not current:
            return []
        result: list[MapNode] = []
        for nid in current.connections:
            node = self.nodes.get(nid)
            if node:
                result.append(node)
        return result

    # ================================================================
    # 锁定/解锁
    # ================================================================

    def unlock_node(self, node_id: str) -> bool:
        """解锁指定节点。"""
        node = self.nodes.get(node_id)
        if node:
            node.unlock()
            return True
        return False

    def lock_node(self, node_id: str) -> bool:
        """锁定指定节点。"""
        node = self.nodes.get(node_id)
        if node:
            node.lock()
            return True
        return False

    def unlock_by_chapter(self, chapter: str) -> int:
        """根据章节解锁所有匹配的节点，返回解锁数量。"""
        count = 0
        for node in self.nodes.values():
            if node.chapter == chapter and node.is_locked:
                node.unlock()
                count += 1
        return count

    # ================================================================
    # 查询
    # ================================================================

    @property
    def visited_nodes(self) -> list[MapNode]:
        """获取所有已访问节点。"""
        return [n for n in self.nodes.values() if n.visited]

    @property
    def locked_nodes(self) -> list[MapNode]:
        """获取所有锁定节点。"""
        return [n for n in self.nodes.values() if n.is_locked]

    @property
    def unlocked_nodes(self) -> list[MapNode]:
        """获取所有已解锁节点。"""
        return [n for n in self.nodes.values() if not n.is_locked]

    # ================================================================
    # 序列化
    # ================================================================

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "current_node": self.current_node,
            "edges": {a: {b: dict(info) for b, info in targets.items()}
                      for a, targets in self.edges.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MapGraph":
        """从字典反序列化。"""
        graph = cls()
        for nid, nd in data.get("nodes", {}).items():
            graph.add_node(MapNode.from_dict(nd))
        graph.current_node = data.get("current_node")
        for a, targets in (data.get("edges") or {}).items():
            for b, info in targets.items():
                graph.edges.setdefault(a, {})[b] = dict(info)
        return graph

    def __repr__(self) -> str:
        n_edges = sum(len(v) for v in self.edges.values()) // 2
        return (f"MapGraph({len(self.nodes)} nodes, {n_edges} edges, "
                f"current={self.current_node})")
