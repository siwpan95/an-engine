# -*- coding: utf-8 -*-
"""
allin_engine.media.ca —— CA 规则引擎（J2 S3，2026-08-25）

自 cellular_automaton 并入：141 规则（Life-like 63 / Multi-state 9 / Complex 11 /
连续 58：Gray-Scott/Lenia/LtL/1D/其他），JSON 规则库 + 统一 RuleManager。

与 pywallpaper 配方谱系分层共存：方案 A（2026-08-25）后 CAPrimitive 恒走配方公式
（evolution.rule 为唯一真相，ca_kernel 退役为史料）；本包是整数态规则引擎超集。
"""

from allin_engine.media.ca.automaton import CellularAutomaton
from allin_engine.media.ca.rules import RULES
from allin_engine.media.ca.rules.rule_manager import RuleManager

__all__ = [
    "CellularAutomaton",
    "RuleManager",
    "RULES",
]
