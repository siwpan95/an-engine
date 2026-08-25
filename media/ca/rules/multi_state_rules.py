"""Multi-state cellular automaton rules.

Includes:
  - Brian's Brain (3 states)
  - Wireworld (4 states)
  - Forest Fire (3 states)
  - Crystal Growth (3 states)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from numpy.typing import NDArray

from alloy.media.ca.rules.base import CARule, count_neighbours, count_von_neumann_neighbours


class BriansBrainRule(CARule):
    """Brian's Brain CA rule.

    3 states:
    - 0: dead (off)
    - 1: alive (on)
    - 2: dying (fade)

    Rules:
    - dead -> alive only if exactly 2 alive neighbours
    - alive -> dying
    - dying -> dead
    """

    def __init__(self) -> None:
        super().__init__("brians_brain", num_states=3)

    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        alive_grid = (grid == 1).astype(np.uint8)
        if neighbours is None or grid.shape != neighbours.shape:
            alive_neighbours = count_neighbours(alive_grid)
        else:
            alive_neighbours = neighbours

        new_grid = np.zeros_like(grid)
        new_grid[grid == 1] = 2
        new_grid[(grid == 0) & (alive_neighbours == 2)] = 1
        return new_grid


class WireworldRule(CARule):
    """Wireworld CA rule.

    4 states:
    - 0: empty
    - 1: conductor
    - 2: electron head
    - 3: electron tail

    Rules:
    - empty -> empty
    - electron head -> electron tail
    - electron tail -> conductor
    - conductor -> electron head if exactly 1 or 2 electron head neighbours
    """

    def __init__(self) -> None:
        super().__init__("wireworld", num_states=4)

    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        head_grid = (grid == 2).astype(np.uint8)
        head_neighbours = count_neighbours(head_grid)

        new_grid = np.zeros_like(grid)
        new_grid[grid == 2] = 3
        new_grid[grid == 3] = 1
        new_grid[(grid == 1) & ((head_neighbours == 1) | (head_neighbours == 2))] = 2
        new_grid[(grid == 1) & (head_neighbours != 1) & (head_neighbours != 2)] = 1
        return new_grid


class ForestFireRule(CARule):
    """Forest Fire CA rule.

    3 states:
    - 0: empty
    - 1: tree
    - 2: burning

    Rules:
    - empty -> tree with probability p_grow
    - tree -> burning if any neighbour is burning
    - burning -> empty
    - tree -> burning with lightning_prob (spontaneous)
    """

    def __init__(self, grow_prob: float = 0.01, lightning_prob: float = 0.001) -> None:
        super().__init__("forest_fire", num_states=3)
        self.grow_prob = grow_prob
        self.lightning_prob = lightning_prob

    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        burning_grid = (grid == 2).astype(np.uint8)
        burning_neighbours = count_neighbours(burning_grid)

        new_grid = np.zeros_like(grid)
        new_grid[(grid == 1) & (burning_neighbours > 0)] = 2
        new_grid[(grid == 1) & (burning_neighbours == 0)] = 1
        new_grid[(grid == 0) & (np.random.random(grid.shape) < self.grow_prob)] = 1
        new_grid[(grid == 1) & (np.random.random(grid.shape) < self.lightning_prob)] = 2
        return new_grid


class CrystalGrowthRule(CARule):
    """Crystal growth CA rule for snowflake-like patterns.

    3 states:
    - 0: empty (water vapor)
    - 1: crystal (frozen)
    - 2: boundary (growing edge)

    Rules:
    - empty -> crystal if enough crystal neighbours (nucleation)
    - crystal stays crystal
    - boundary -> crystal (growth)
    """

    def __init__(self, growth_threshold: int = 3, freeze_prob: float = 0.1) -> None:
        super().__init__("crystal_growth", num_states=3)
        self.growth_threshold = growth_threshold
        self.freeze_prob = freeze_prob

    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        crystal_grid = (grid == 1).astype(np.uint8)
        crystal_neighbours = count_neighbours(crystal_grid)

        new_grid = grid.copy()
        new_grid[(grid == 0) & (crystal_neighbours >= self.growth_threshold)] = 1
        new_grid[(grid == 0) & (np.random.random(grid.shape) < self.freeze_prob)] = 1
        new_grid[grid == 2] = 1
        return new_grid


def register_multi_state_rules(registry: dict) -> None:
    """Register all multi-state rules."""
    registry["brians_brain"] = BriansBrainRule()
    registry["wireworld"] = WireworldRule()
    registry["forest_fire"] = ForestFireRule()
    registry["crystal_growth"] = CrystalGrowthRule()


# ======================================================================
# Sandpile rule — Abelian sandpile model
# ======================================================================

class SandpileRule(CARule):
    """Abelian Sandpile CA rule.

    Models the Abelian sandpile where cells accumulate grains and
    topple when reaching a threshold, sending one grain to each
    von Neumann (cardinal) neighbour.

    States 0..threshold-1 represent stable grain counts.
    A cell at threshold topples, distributing grains and reducing.
    """

    def __init__(self, threshold: int = 4, num_states: int = 4) -> None:
        super().__init__("sandpile", num_states=num_states)
        self.threshold = threshold

    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        """Apply sandpile toppling rule.

        Each cell with >= threshold-1 grains topples:
        - sends 1 grain to each von Neumann neighbour
        - loses threshold grains itself
        - result is clipped to valid state range
        """
        # Count how many unstable neighbours each cell has
        unstable = (grid >= self.threshold - 1).astype(np.uint8)
        unstable_neighbours = count_von_neumann_neighbours(unstable)

        # Build new state: current + incoming grains from toppling neighbours
        new_grid = grid.astype(np.int32) + unstable_neighbours

        # Unstable cells lose threshold grains (one per cardinal direction)
        new_grid[unstable.astype(bool)] -= self.threshold

        # Clip to valid range [0, num_states-1]
        np.clip(new_grid, 0, self.num_states - 1, out=new_grid)

        return new_grid.astype(np.uint8)
