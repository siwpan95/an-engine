# -*- coding: utf-8 -*-
"""an-engine 的 bridge 友好接口（**新增文件，不改既有模块**）。

给「超级引擎」组合仓（superengine）用的稳定入口。

关键取舍：**托管而非替换**
--------------------------
本仓 `core/context.py` 自述「源自 Cordis 的三个核心算子」（`provide`/`get`/`effect`、
dispose 逆序栈、`install(name/inject/apply)`、`fork`/`scopes`），且**刻意零第三方依赖**。
因此组合仓不把 cordis 塞进来替换它，而是**托管**：外层 cordis 负责生命周期与回滚，
内层仍是本仓自己的 `Context`，零依赖不变、既有测试基线不变。

本文件只做三件事：造 Context、按 worldspec 建 MapGraph、把能力挂进 Context。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = [
    "BRIDGE_VERSION",
    "SUPPORTED_CONTRACTS",
    "new_context",
    "mapgraph_from_worldspec",
    "provide_mapgraph",
    "route",
    "nearest",
]

BRIDGE_VERSION = "1.0.0"

#: 本仓声明能满足的契约及兼容区间 —— 由组合仓在装配期校验
SUPPORTED_CONTRACTS = {
    "gameplay_world": ">=1.0,<2.0",
    "mapgraph_source": ">=1.0,<2.0",
}


def new_context():
    """新建一个本仓的 `Context`（可逆装配容器）。

    零第三方依赖：只 import 本仓 `core.context`，**不 import cordis**。
    """
    from .core.context import Context

    return Context()


def mapgraph_from_worldspec(spec_dir, *, strict: bool = False):
    """从 worldspec v1 目录构造 `MapGraph`（玩法侧读世界契约的入口）。"""
    from .world.map_graph import MapGraph

    return MapGraph.from_worldspec(spec_dir, strict=strict)


def provide_mapgraph(ctx, graph, key: str = "mapgraph") -> Any:
    """把 MapGraph 挂进 Context；返回 ``ctx`` 便于链式调用。

    ``dispose`` 交给 Context 自己的 dispose 栈：外层卸载时随 Context 一起回滚。
    """
    ctx.provide(key, graph)
    return ctx


def nearest(graph, x: float, z: float, **kw):
    """最近节点查询（转发 `MapGraph.nearest`）。"""
    return graph.nearest(x, z, **kw)


def route(graph, start: str, goal: str, **kw) -> List[str]:
    """最短路（转发 `MapGraph.route`）。"""
    return graph.route(start, goal, **kw)
