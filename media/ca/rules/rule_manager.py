"""Rule Manager — unified Python program that manages all rules' JSON files.

Reads rule definitions from JSON files in rules/json/ directory,
dynamically constructs rule instances, and maintains the global RULES registry.

Architecture:
  - JSON files contain rule definitions (names, parameters, presets, descriptions)
  - Python classes (in base.py, complex_rules.py, etc.) contain computation logic
  - This manager bridges the two: it reads JSON → creates Python rule objects

Adding new rules:
  - For 2-state Life-like rules: just add entries to life_rules.json
  - For preset variants: add entries to the appropriate JSON file
  - For entirely new rule types: add a JSON file + a Python class + register here
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alloy.media.ca.rules.base import CARule, OuterTotalisticRule
from alloy.media.ca.rules.complex_rules import (
    LangtonsLoopRule,
    SnowflakeRule,
    CyclicCARule,
    HodgepodgeRule,
)
from alloy.media.ca.rules.multi_state_rules import (
    BriansBrainRule,
    WireworldRule,
    ForestFireRule,
    CrystalGrowthRule,
    SandpileRule,
)
from alloy.media.ca.rules.continuous_rules import (
    GrayScottRule,
    LeniaRule,
    LargerThanLifeRule,
    Elementary1DRule,
    SmoothLifeRule,
    BZReactionRule,
)

# Directory containing JSON rule definition files
_JSON_DIR: Path = Path(__file__).parent / "json"


# ======================================================================
# Rule type factory map
# ======================================================================
# Maps rule_type strings (from JSON) to their Python class constructors.
# Each factory takes (name, **params) and returns a CARule instance.

_SIMPLE_FACTORIES: dict[str, type[CARule]] = {
    "brians_brain": BriansBrainRule,
    "wireworld": WireworldRule,
    "langtons_loop": LangtonsLoopRule,
}


class RuleManager:
    """Manages all CA rule definitions loaded from JSON files.

    Responsibilities:
      1. Load all JSON rule definition files from rules/json/
      2. Build CARule instances from JSON data
      3. Maintain a global RULES registry (name → CARule)
      4. Support runtime rule lookup, listing, and switching
      5. Provide metadata (descriptions, categories) for UI display
    """

    def __init__(self) -> None:
        self._rules: dict[str, CARule] = {}
        self._descriptions: dict[str, str] = {}
        self._categories: dict[str, str] = {}
        self._load_all_json()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_all_json(self) -> None:
        """Load all JSON files from the rules/json/ directory."""
        if not _JSON_DIR.exists():
            raise FileNotFoundError(f"JSON rules directory not found: {_JSON_DIR}")

        for json_file in sorted(_JSON_DIR.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                self._process_json(data, json_file.stem)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"[RuleManager] Warning: Failed to load {json_file.name}: {e}")

    def _process_json(self, data: dict[str, Any], filename: str) -> None:
        """Process a single JSON file's data and register rules.

        Uses 'rule_family' field in JSON for dispatching to the correct
        builder. Falls back to filename-based detection for backwards compat.
        """
        category = data.get("category", filename.replace("_rules", ""))
        rule_type = data.get("rule_type", None)
        rule_family = data.get("rule_family", None)

        # --- Outer-totalistic (2-state B/S) rules ---
        if rule_type == "outer_totalistic":
            for entry in data.get("rules", []):
                name = entry["name"]
                born = set(entry["born"])
                survive = set(entry["survive"])
                desc = entry.get("description", "")
                rule = OuterTotalisticRule(name, born, survive)
                self._register(name, rule, desc, category)

        # --- Multi-state rules ---
        elif category == "multi_state":
            for entry in data.get("rules", []):
                self._build_multi_state_rule(entry, category)

        # --- Complex rules ---
        elif category == "complex":
            for entry in data.get("rules", []):
                self._build_complex_rule(entry, category)

        # --- Gray-Scott rules ---
        elif rule_family == "gray_scott":
            presets = data.get("presets", {})
            for entry in data.get("rules", []):
                self._build_gray_scott_rule(entry, presets, category)

        # --- Lenia rules ---
        elif rule_family == "lenia":
            species_params = data.get("species_params", {})
            for entry in data.get("rules", []):
                self._build_lenia_rule(entry, species_params, category)

        # --- Larger than Life rules ---
        elif rule_family == "larger_than_life":
            presets = data.get("presets", {})
            for entry in data.get("rules", []):
                self._build_ltl_rule(entry, presets, category)

        # --- Elementary 1D rules ---
        elif rule_family == "elementary_1d":
            for entry in data.get("rules", []):
                self._build_elementary_1d_rule(entry, category)

        # --- Other continuous rules ---
        elif rule_family == "other_continuous":
            for entry in data.get("rules", []):
                self._build_other_continuous_rule(entry, category)

    # ------------------------------------------------------------------
    # Rule builders
    # ------------------------------------------------------------------

    def _register(
        self, name: str, rule: CARule, description: str, category: str,
    ) -> None:
        """Register a rule in all internal dictionaries."""
        self._rules[name] = rule
        self._descriptions[name] = description
        self._categories[name] = category

    def _build_multi_state_rule(self, entry: dict, category: str) -> None:
        """Build a multi-state rule from JSON entry."""
        name = entry["name"]
        rule_type = entry.get("rule_type", name)
        desc = entry.get("description", "")
        params = entry.get("params", {})

        factory = _SIMPLE_FACTORIES.get(rule_type)

        if rule_type == "forest_fire":
            rule = ForestFireRule(**params)
            rule.name = name
        elif rule_type == "crystal_growth":
            rule = CrystalGrowthRule(**params)
            rule.name = name
        elif rule_type == "sandpile":
            rule = SandpileRule(**params)
            rule.name = name
        elif factory is not None:
            rule = factory()
            rule.name = name
        else:
            print(f"[RuleManager] Unknown multi_state rule type: {rule_type}")
            return

        self._register(name, rule, desc, category)

    def _build_complex_rule(self, entry: dict, category: str) -> None:
        """Build a complex rule from JSON entry."""
        name = entry["name"]
        rule_type = entry.get("rule_type", name)
        desc = entry.get("description", "")
        params = entry.get("params", {})

        if rule_type == "langtons_loop":
            rule = LangtonsLoopRule()
            rule.name = name
        elif rule_type == "snowflake":
            rule = SnowflakeRule(**params)
            rule.name = name
        elif rule_type == "cyclic":
            rule = CyclicCARule(**params)
            rule.name = name
        elif rule_type == "hodgepodge":
            rule = HodgepodgeRule(**params)
            rule.name = name
        else:
            print(f"[RuleManager] Unknown complex rule type: {rule_type}")
            return

        self._register(name, rule, desc, category)

    def _build_gray_scott_rule(
        self, entry: dict, presets: dict[str, Any], category: str,
    ) -> None:
        """Build a Gray-Scott rule from JSON entry + presets."""
        name = entry["name"]
        preset_name = entry.get("preset", "spots")
        desc = entry.get("description", "")

        # Get preset parameters
        preset_params = presets.get(preset_name, {"f": 0.035, "k": 0.065})
        rule = GrayScottRule(
            preset=preset_name,
            Du=preset_params.get("Du", 0.16),
            Dv=preset_params.get("Dv", 0.08),
        )
        rule.name = name
        rule.f = preset_params.get("f", 0.035)
        rule.k = preset_params.get("k", 0.065)

        self._register(name, rule, desc, category)

    def _build_lenia_rule(
        self, entry: dict, species_params: dict[str, Any], category: str,
    ) -> None:
        """Build a Lenia rule from JSON entry + species params."""
        name = entry["name"]
        species = entry.get("species", "orbium")
        desc = entry.get("description", "")

        sp = species_params.get(species, {})
        rule = LeniaRule(
            kernel_radius=sp.get("kernel_radius", 13),
            mu=sp.get("mu", 0.15),
            sigma=sp.get("sigma", 0.015),
            dt=sp.get("dt", 0.1),
            species=species,
        )
        rule.name = name

        self._register(name, rule, desc, category)

    def _build_ltl_rule(
        self, entry: dict, presets: dict[str, Any], category: str,
    ) -> None:
        """Build a Larger than Life rule from JSON entry + presets."""
        name = entry["name"]
        preset_name = entry.get("preset", "bugs")
        desc = entry.get("description", "")

        ps = presets.get(preset_name, {})
        rule = LargerThanLifeRule(
            radius=ps.get("radius", 5),
            born_min=ps.get("born_min", 34),
            born_max=ps.get("born_max", 45),
            survive_min=ps.get("survive_min", 34),
            survive_max=ps.get("survive_max", 58),
            preset=preset_name,
        )
        rule.name = name

        self._register(name, rule, desc, category)

    def _build_elementary_1d_rule(self, entry: dict, category: str) -> None:
        """Build an Elementary 1D CA rule from JSON entry."""
        name = entry["name"]
        rule_number = entry.get("rule_number", 30)
        desc = entry.get("description", "")

        rule = Elementary1DRule(rule_number=rule_number)
        rule.name = name

        self._register(name, rule, desc, category)

    def _build_other_continuous_rule(self, entry: dict, category: str) -> None:
        """Build other continuous rules (SmoothLife, BZ Reaction) from JSON."""
        name = entry["name"]
        rule_type = entry.get("rule_type", name)
        desc = entry.get("description", "")
        params = entry.get("params", {})

        if rule_type == "smooth_life":
            rule = SmoothLifeRule(**params)
            rule.name = name
        elif rule_type == "bz_reaction":
            rule = BZReactionRule(**params)
            rule.name = name
        else:
            print(f"[RuleManager] Unknown continuous rule type: {rule_type}")
            return

        self._register(name, rule, desc, category)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_rule(self, name: str) -> CARule | None:
        """Get a rule by name."""
        return self._rules.get(name)

    def list_rules(self) -> list[str]:
        """List all available rule names (sorted)."""
        return sorted(self._rules.keys())

    def list_rules_by_category(self) -> dict[str, list[str]]:
        """Group rule names by category."""
        result: dict[str, list[str]] = {}
        for name, cat in self._categories.items():
            result.setdefault(cat, []).append(name)
        for cat in result:
            result[cat].sort()
        return result

    def get_description(self, name: str) -> str:
        """Get a rule's description."""
        return self._descriptions.get(name, "")

    def get_category(self, name: str) -> str:
        """Get a rule's category."""
        return self._categories.get(name, "")

    @property
    def rules(self) -> dict[str, CARule]:
        """Access the full rules registry."""
        return self._rules

    @property
    def total_count(self) -> int:
        """Total number of registered rules."""
        return len(self._rules)

    def reload(self) -> None:
        """Reload all JSON files (useful for hot-updating rules)."""
        self._rules.clear()
        self._descriptions.clear()
        self._categories.clear()
        self._load_all_json()

# ======================================================================
# Global instance — the single source of truth for all rules
# ======================================================================

_manager = RuleManager()
RULES: dict[str, CARule] = _manager.rules
total_count: int = _manager.total_count


def get_rule(name: str) -> CARule | None:
    """Get a rule by name from the registry."""
    return RULES.get(name)


def list_rules() -> list[str]:
    """List all available rule names."""
    return _manager.list_rules()


def get_description(name: str) -> str:
    """Get a rule's description."""
    return _manager.get_description(name)


def get_category(name: str) -> str:
    """Get a rule's category."""
    return _manager.get_category(name)


def list_rules_by_category() -> dict[str, list[str]]:
    """Group rule names by category."""
    return _manager.list_rules_by_category()


def reload_rules() -> None:
    """Reload all JSON rule files."""
    global RULES, total_count
    _manager.reload()
    RULES = _manager.rules
    total_count = _manager.total_count


__all__ = [
    "CARule", "OuterTotalisticRule", "RULES",
    "RuleManager", "SandpileRule",
    "count_neighbours", "count_von_neumann_neighbours",
    "get_rule", "list_rules", "get_description", "get_category",
    "list_rules_by_category", "reload_rules",
]
