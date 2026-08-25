"""Core Cellular Automaton logic: grid storage, evolution, cell manipulation.

Supports both 2-state and multi-state cellular automata through a unified
rule interface. Uses numpy arrays for efficient computation.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from numpy.typing import NDArray

from alloy.media.ca.rules.base import CARule
from alloy.media.ca.rules import RULES


class CellularAutomaton:
    """Manages the grid state and evolves it according to a CA rule.

    Supports both 2-state and multi-state cellular automata.

    Attributes:
        grid:    2D uint8 array — cell states (0 to num_states-1)
        age:     2D int32 array — generations a cell has been in current state
        trail:   2D int32 array — frames since death (0 = alive or long dead)
        rule:    The active CARule
        rows:    Grid height in cells
        cols:    Grid width in cells
        num_states: Number of states in the current rule
    """

    def __init__(
        self,
        rows: int,
        cols: int,
        rule_name: str = "game_of_life",
        initial_density: float = 0.25,
        trail_length: int = 12,
    ) -> None:
        self.rows = rows
        self.cols = cols
        self.trail_length = trail_length

        rule = RULES.get(rule_name)
        if rule is None:
            rule = RULES["game_of_life"]
        self.rule: CARule = rule
        self.num_states = rule.num_states

        self.grid: NDArray[np.uint8] = np.zeros((rows, cols), dtype=np.uint8)
        self.age: NDArray[np.int32] = np.zeros((rows, cols), dtype=np.int32)
        self.trail: NDArray[np.int32] = np.zeros((rows, cols), dtype=np.int32)

        self.randomize(initial_density)

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def randomize(self, density: float = 0.25) -> None:
        """Fill the grid with random states.

        For 2-state CA: cells are either dead (0) or alive (1).
        For multi-state CA: cells are randomly assigned a state
        based on the rule.
        For continuous/1D rules: initialize accordingly.
        """
        # --- Continuous rules: reset their internal state ---
        if hasattr(self.rule, 'has_float_state') and self.rule.has_float_state:
            if hasattr(self.rule, 'reset'):
                self.rule.reset((self.rows, self.cols))
            # Initialize with step to populate grid
            self.grid = self.rule.step(self.grid)
            self.age = np.zeros((self.rows, self.cols), dtype=np.int32)
            self.trail = np.zeros((self.rows, self.cols), dtype=np.int32)
            return

        # --- 1D Elementary CA: special initialization ---
        if self.rule.name in ("elementary_1d",) or self.rule.name.startswith("wolfram_"):
            if hasattr(self.rule, 'init_grid'):
                self.grid = self.rule.init_grid(self.rows, self.cols)
            else:
                self.grid = (np.random.random((self.rows, self.cols)) < density).astype(np.uint8)
            self.age = np.zeros((self.rows, self.cols), dtype=np.int32)
            self.trail = np.zeros((self.rows, self.cols), dtype=np.int32)
            return

        if self.num_states == 2:
            self.grid = (np.random.random((self.rows, self.cols)) < density).astype(np.uint8)
        else:
            if self.rule.name in ("wireworld", "langtons_loop"):
                self.grid = np.random.choice(
                    [0, 1, 1, 1, 2],
                    size=(self.rows, self.cols),
                ).astype(np.uint8)
            elif self.rule.name == "snowflake":
                max_s = self.num_states - 1
                self.grid = np.random.choice(
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, max_s],
                    size=(self.rows, self.cols),
                ).astype(np.uint8)
            elif self.rule.name == "bz_reaction":
                # Sparse initial state: mostly resting, few excited seeds
                self.grid = np.zeros((self.rows, self.cols), dtype=np.uint8)
                num_seeds = max(3, (self.rows * self.cols) // 500)
                rng = np.random.default_rng()
                for _ in range(num_seeds):
                    r = rng.integers(0, self.rows)
                    c = rng.integers(0, self.cols)
                    radius = rng.integers(3, 10)
                    for dr in range(-radius, radius + 1):
                        for dc in range(-radius, radius + 1):
                            if dr * dr + dc * dc <= radius * radius:
                                rr = (r + dr) % self.rows
                                cc = (c + dc) % self.cols
                                self.grid[rr, cc] = rng.integers(1, 3)
            else:
                self.grid = np.random.randint(
                    0, self.num_states,
                    size=(self.rows, self.cols),
                    dtype=np.uint8,
                )

        self.age = np.zeros((self.rows, self.cols), dtype=np.int32)
        self.trail = np.zeros((self.rows, self.cols), dtype=np.int32)

    def clear(self) -> None:
        """Set all cells to state 0 and reset age/trail."""
        self.grid[:] = 0
        self.age[:] = 0
        self.trail[:] = 0

    def load_pattern(
        self, pattern_name: str, row: int = 0, col: int = 0,
        clear_first: bool = True,
    ) -> None:
        """Load a predefined pattern onto the grid."""
        # Lazy import to avoid circular dependency with rendering
        from rendering.patterns import get_pattern, place_pattern

        pattern = get_pattern(pattern_name)
        if pattern is None:
            raise ValueError(f"Unknown pattern: {pattern_name}")

        if clear_first:
            self.clear()

        place_pattern(self.grid, pattern, row, col, clear_first=False)
        self.age = self.grid.astype(np.int32)
        self.trail = np.zeros((self.rows, self.cols), dtype=np.int32)

    # ------------------------------------------------------------------
    # Evolution
    # ------------------------------------------------------------------

    def step(self) -> None:
        """Advance the automaton by one generation."""
        is_continuous = (
            hasattr(self.rule, 'has_float_state') and self.rule.has_float_state
        )
        new_grid = self.rule.step(self.grid)

        if not is_continuous:
            # Update trails (for discrete CA)
            if self.num_states == 2:
                just_died = (self.grid == 1) & (new_grid == 0)
                self.trail[just_died] = self.trail_length
                still_dead = (self.grid == 0) & (new_grid == 0)
                self.trail[still_dead] = np.maximum(0, self.trail[still_dead] - 1)
                self.trail[new_grid == 1] = 0

            # Update age
            same_state = new_grid == self.grid
            self.age = np.where(same_state, self.age + 1, 1).astype(np.int32)

        self.grid = new_grid

    # ------------------------------------------------------------------
    # Cell manipulation
    # ------------------------------------------------------------------

    def toggle_cell(self, row: int, col: int) -> None:
        """Toggle a single cell between states."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.grid[row, col] = (self.grid[row, col] + 1) % self.num_states
            self.age[row, col] = 1

    def set_cell(self, row: int, col: int, state: int = 1) -> None:
        """Set a single cell to a specific state."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.grid[row, col] = state
            self.age[row, col] = 1

    # ------------------------------------------------------------------
    # Rule switching
    # ------------------------------------------------------------------

    def set_rule(self, rule_name: str) -> None:
        """Switch to a different CA rule by name."""
        rule = RULES.get(rule_name)
        if rule is not None:
            self.rule = rule
            self.num_states = rule.num_states
            self.clear()
            # Reset continuous rules' internal float state (e.g. Gray-Scott U/V fields)
            if hasattr(rule, 'reset'):
                rule.reset(self.grid.shape)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def alive_count(self) -> int:
        """Total number of 'alive' cells (state > 0)."""
        return int((self.grid > 0).sum())

    def state_count(self, state: int) -> int:
        """Count cells in a specific state."""
        return int((self.grid == state).sum())
