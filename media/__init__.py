# -*- coding: utf-8 -*-
"""
alloy.media —— 媒体子系统（J2 S2，2026-08-25）

自 pywallpaper 能力层并入：公式引擎（media 域）+ 效果原语 + CA 配方。
"""

from alloy.media.formula_engine import FormulaEngine
from alloy.media.core import EngineEffect
from alloy.media.effect_loader import load_engine_effects, create_effect

__all__ = [
    "FormulaEngine",
    "EngineEffect",
    "load_engine_effects",
    "create_effect",
]
