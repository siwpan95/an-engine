# -*- coding: utf-8 -*-
"""
allin_engine.media —— 媒体子系统（J2 S2，2026-08-25）

自 pywallpaper 能力层并入：公式引擎（media 域）+ 效果原语 + CA 配方。
"""

from allin_engine.media.formula_engine import FormulaEngine
from allin_engine.media.core import EngineEffect
from allin_engine.media.effect_loader import load_engine_effects, create_effect

__all__ = [
    "FormulaEngine",
    "EngineEffect",
    "load_engine_effects",
    "create_effect",
]
