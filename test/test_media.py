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


def test_media_ca_formula_single_path():
    """方案 A：CAPrimitive 不再引用 JIT 核，配方公式为唯一真相。"""
    from pathlib import Path
    from alloy.media.primitives import ca as ca_mod

    assert ca_mod.HAS_NUMBA is False
    src = Path(ca_mod.__file__).read_text(encoding="utf-8")
    assert "from alloy.media.primitives.ca_kernel" not in src


def test_media_ca_kernel_retired():
    """方案 A：ca_kernel 已退役为只读史料。"""
    from alloy.media.primitives import ca_kernel

    assert getattr(ca_kernel, "__retired__", False) is True


def test_media_ca_bz_formula_semantics():
    """方案 A 修复目标：BZ 配方公式语义成为唯一真相。

    BZ 公式 `1 if (c>0.5) else (0.5 if sum_n>1 else c)`：
    - 活细胞（c>0.5）下一步恒为 1；
    - 死细胞邻居和 >1 时变为 0.5，否则保持。
    （旧 JIT 核对 BZ 用连续松弛模型，与公式不一致——已退役。）
    """
    import numpy as np
    from alloy.media.formula_engine import FormulaEngine

    eng = FormulaEngine()
    rule = eng.compile("1 if (c > 0.5) else (0.5 if sum_n > 1 else c)", ["c", "sum_n"])
    g = np.zeros((8, 8), dtype=np.float32)
    g[2, 3] = 1.0
    g[4, 3] = 1.0
    sum_n = (
        np.roll(g, 1, 0) + np.roll(g, -1, 0) + np.roll(g, 1, 1) + np.roll(g, -1, 1)
        + np.roll(np.roll(g, 1, 0), 1, 1) + np.roll(np.roll(g, 1, 0), -1, 1)
        + np.roll(np.roll(g, -1, 0), 1, 1) + np.roll(np.roll(g, -1, 0), -1, 1)
    )
    v = np.asarray(rule(c=g, sum_n=sum_n), dtype=np.float32)
    assert v[2, 3] == 1.0        # 活细胞 → 1
    assert v[3, 3] == 0.5        # 2 邻居的死细胞 → 0.5
    assert v[0, 0] == 0.0        # 无邻居死细胞 → 保持 0


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
