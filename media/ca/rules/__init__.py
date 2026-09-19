"""Rule definitions and registry for Cellular Automaton.

Now driven by JSON rule definitions via RuleManager.
All rule data (names, parameters, presets, descriptions) is loaded from
JSON files in rules/json/. Python classes provide computation logic only.

Supports 2-state, multi-state, complex, continuous, and 1D cellular automata.
"""

from __future__ import annotations

from allin_engine.media.ca.rules.base import CARule, OuterTotalisticRule, count_neighbours, count_von_neumann_neighbours
from allin_engine.media.ca.rules.multi_state_rules import SandpileRule
from allin_engine.media.ca.rules.rule_manager import (
    RuleManager,
    RULES,
    total_count,
    get_rule,
    list_rules,
    get_description,
    get_category,
    list_rules_by_category,
    reload_rules,
)


__all__ = [
    "CARule", "OuterTotalisticRule", "RULES",
    "RuleManager", "SandpileRule",
    "count_neighbours", "count_von_neumann_neighbours",
    "get_rule", "list_rules", "get_description", "get_category",
    "list_rules_by_category", "reload_rules", "total_count",
]
