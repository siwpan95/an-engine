# -*- coding: utf-8 -*-
"""
alloy.media.ca —— CA 规则引擎（J2 S3，2026-08-25）

自 cellular_automaton 并入：141 规则（Life-like 63 / Multi-state 9 / Complex 11 /
连续 58：Gray-Scott/Lenia/LtL/1D/其他），JSON 规则库 + 统一 RuleManager。

与 pywallpaper 配方内核（alloy.media.primitives.ca_kernel，4973 配方兼容层）
分层共存：ca_kernel 服务 pywallpaper 效果配方语料，本包是通用规则引擎超集。
"""

from alloy.media.ca.automaton import CellularAutomaton
from alloy.media.ca.rules import RULES
from alloy.media.ca.rules.rule_manager import RuleManager

__all__ = [
    "CellularAutomaton",
    "RuleManager",
    "RULES",
]
