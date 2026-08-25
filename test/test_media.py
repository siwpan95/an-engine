# -*- coding: utf-8 -*-
"""
test_media.py —— 媒体子系统冒烟（J2 S2）
"""

from __future__ import annotations

import os
from pathlib import Path


def test_media_formula_engine():
    from alloy.media.formula_engine import FormulaEngine
    engine = FormulaEngine()
    func = engine.compile("sin(t)", ["t"])
    result = func(t=0.5)
    assert abs(result - 0.479425538604203) < 0.01


def test_media_primitives_importable():
    import importlib
    prim_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent / "media" / "primitives"
    names = [p.stem for p in sorted(prim_dir.glob("*.py")) if not p.stem.startswith("_")]
    assert len(names) >= 20
    for n in ("ca", "fluid", "particle", "curve", "formula"):
        importlib.import_module(f"alloy.media.primitives.{n}")


def test_media_recipes_count():
    from pathlib import Path
    rec = Path(os.path.dirname(os.path.abspath(__file__))).parent / "media" / "recipes"
    n = len(list(rec.glob("*.json")))
    assert n >= 4000


def test_media_ca_engine():
    """CA 规则引擎（J2 S3 自 cellular_automaton 并入）：141 规则加载 + 演化。"""
    from alloy.media.ca import CellularAutomaton
    from alloy.media.ca.rules.rule_manager import RuleManager

    m = RuleManager()
    assert m.total_count >= 140
    assert set(m.list_rules_by_category()) >= {"life", "multi_state", "complex", "continuous"}
    ca = CellularAutomaton(20, 20, "game_of_life", initial_density=0.3)
    ca.step()
    assert ca.grid.shape == (20, 20)


def test_media_preset_assembly():
    """profile "media" 装配后 Context 持有 media 服务（dump-profile 显示 media 子系统）。"""
    from alloy.core.context import Context
    from alloy.core.profiles import assemble_profile

    ctx = Context()
    try:
        assemble_profile(ctx, ["core", "world", "media"])
        assert ctx.has("media")
        assert type(ctx.get("media")).__name__ == "FormulaEngine"
    finally:
        ctx.dispose()
