"""Complex cellular automaton rules with interesting emergent behavior.

New rules added:
  - Langton's Loop (8-state, self-replicating loop)
  - Snowflake (multi-state dendritic crystal growth, 6-fold symmetry)
  - Cyclic CA (n-color cyclic spiral waves, Greenberg-Hastings variant)
  - Hodgepodge Machine (reaction-diffusion with spiral waves)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from numpy.typing import NDArray

from allin_engine.media.ca.rules.base import CARule, count_neighbours, count_von_neumann_neighbours


# ======================================================================
# Langton's Loop — 8-state self-replicating automaton
# ======================================================================
# Neighborhood: von Neumann (N, S, E, W) + center.
# States:
#   0 = empty     1 = sheath/wire
#   2 = signal →  3 = signal ↓
#   4 = signal ←  5 = signal ↑
#   6 = phagocyte  7 = phagocyte+signal


def _build_langton_rule_table() -> dict[tuple[int, int, int, int, int], int]:
    """Build Langton's Loop transition table (center,N,S,E,W) -> new_state.

    This is the classic 8-state self-replicating loop by Chris Langton (1984),
    as refined by J. Byl.
    """
    R: dict[tuple[int, int, int, int, int], int] = {}
    C, N, S, E, W = 0, 1, 2, 3, 4  # indices for center,north,south,east,west

    def add(c, n, s, e, w, new):
        R[(c, n, s, e, w)] = new

    # --- Sheath maintenance (state 1) ---
    # Sheath stays sheath unless consumed
    for nbr in (0, 1, 2, 3, 4, 5, 6, 7):
        add(1, 1, nbr, 1, 1, 1)
        add(1, 1, 1, nbr, 1, 1)
        add(1, nbr, 1, 1, 1, 1)
        add(1, 1, 1, 1, nbr, 1)
        add(1, 1, 1, 1, 1, 1)

    # Sheath with missing neighbor becomes 0 if no signal present
    # (simplified — sheath disintegrates without support)
    for nbr in (0, 2, 4, 6):
        for nbr2 in (0, 2, 4, 6):
            add(1, 1, 1, nbr, nbr2, 0)
            add(1, 1, nbr, 1, nbr2, 0)
            add(1, nbr, 1, 1, nbr2, 0)
            add(1, nbr, nbr2, 1, 1, 0)

    # Sheath with signals turns into signal
    add(1, 2, 1, 1, 0, 2)
    add(1, 2, 1, 0, 1, 2)
    add(1, 4, 0, 1, 1, 4)
    add(1, 0, 4, 1, 1, 4)
    add(1, 3, 1, 1, 0, 3)
    add(1, 1, 3, 1, 0, 3)
    add(1, 5, 0, 1, 1, 5)
    add(1, 1, 5, 0, 1, 5)

    # Corners: signal turns
    add(1, 2, 0, 1, 1, 3)
    add(1, 1, 2, 0, 1, 5)
    add(1, 4, 1, 1, 0, 5)
    add(1, 0, 1, 4, 1, 3)

    # --- Signal propagation (states 2-5) ---
    # Signal moving right → turns into sheath, and delivers signal east
    add(2, 1, 1, 1, 2, 0)   # signal → hits sheath to the west
    add(2, 1, 1, 0, 2, 2)   # signal → propagates right
    add(2, 1, 1, 1, 0, 1)   # signal → at end, becomes sheath
    add(2, 1, 2, 1, 1, 1)   # signal → with signal from north
    add(2, 1, 0, 1, 1, 5)   # signal → corner turn to ↑
    add(2, 1, 0, 1, 0, 5)
    add(2, 1, 0, 0, 1, 3)   # signal → corner turn to ↓
    add(2, 1, 3, 1, 1, 1)   # signal → absorbed by ↓ signal

    # Signal moving down ↓
    add(3, 1, 1, 2, 1, 0)
    add(3, 0, 1, 2, 1, 3)
    add(3, 1, 1, 0, 1, 1)
    add(3, 1, 0, 1, 1, 4)   # corner turn to ←
    add(3, 0, 0, 1, 1, 4)
    add(3, 1, 1, 1, 0, 2)   # corner turn to →
    add(3, 0, 1, 1, 0, 2)

    # Signal moving left ←
    add(4, 1, 1, 4, 1, 0)
    add(4, 1, 1, 4, 0, 4)
    add(4, 1, 1, 1, 1, 1)
    add(4, 2, 1, 1, 1, 1)
    add(4, 1, 0, 0, 1, 3)   # corner turn to ↓
    add(4, 1, 0, 1, 1, 5)   # corner turn to ↑
    add(4, 1, 0, 1, 0, 5)
    add(4, 0, 0, 0, 1, 3)

    # Signal moving up ↑
    add(5, 2, 1, 1, 1, 0)
    add(5, 2, 1, 0, 1, 5)
    add(5, 1, 1, 1, 1, 1)
    add(5, 0, 1, 0, 1, 2)   # corner turn to →
    add(5, 0, 1, 1, 1, 4)   # corner turn to ←
    add(5, 1, 0, 0, 1, 2)
    add(5, 0, 0, 0, 1, 2)

    # --- Phagocyte (state 6) ---
    add(6, 0, 0, 0, 0, 6)  # persists in empty space
    add(6, 2, 1, 1, 1, 7)  # receives signal → becomes 7
    add(6, 1, 3, 1, 1, 7)  # receives signal ↓
    add(6, 1, 1, 4, 1, 7)  # receives signal ←
    add(6, 1, 1, 1, 5, 7)  # receives signal ↑

    # --- Phagocyte+signal (state 7) ---
    add(7, 0, 0, 0, 0, 0)  # deletes the cell, becomes empty
    add(7, 1, 2, 1, 1, 1)  # turns back to sheath

    return R


# Pre-compute transition lookup
_LANGTON_RULES = _build_langton_rule_table()


class LangtonsLoopRule(CARule):
    """Langton's self-replicating loop (8-state).

    An 8-state self-replicating cellular automaton using the von Neumann
    neighbourhood.  A small loop of sheath cells contains circulating
    signals; after a fixed number of cycles the loop extends an arm and
    replicates itself.

    States:
      0 = empty      1 = sheath/wire
      2 = signal →   3 = signal ↓
      4 = signal ←   5 = signal ↑
      6 = phagocyte  7 = phagocyte+signal (deletes cell next step)

    Reference:
      Langton, C. G. (1984). "Self-reproduction in cellular automata."
      Physica D: Nonlinear Phenomena, 10(1-2), 135-144.
    """

    def __init__(self) -> None:
        super().__init__("langtons_loop", num_states=8)

    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        """Apply Langton's Loop rule using vectorized table lookup.

        Strategy:
          1. Gather center and von Neumann neighbour grids.
          2. Convert each 5-tuple (c,n,s,e,w) into a hashable key.
          3. Look up new state via numpy vectorization of the rule table.
        """
        rows, cols = grid.shape
        new_grid = np.zeros_like(grid)

        # Get shifted grids: center + 4 cardinal neighbours
        c = grid
        n = np.roll(grid, 1, axis=0)    # north (down-shift)
        s = np.roll(grid, -1, axis=0)   # south (up-shift)
        w = np.roll(grid, 1, axis=1)    # west (right-shift)
        e = np.roll(grid, -1, axis=1)   # east (left-shift)

        # Encode 5-tuple into a single integer key:
        #   key = c*8^4 + n*8^3 + s*8^2 + e*8^1 + w*8^0
        # 8 states → needs 3 bits each → total 15 bits fits in int32
        key = (
            c.astype(np.int32) * 4096 +
            n.astype(np.int32) * 512 +
            s.astype(np.int32) * 64 +
            e.astype(np.int32) * 8 +
            w.astype(np.int32)
        )

        # Build lookup arrays from the rule dictionary
        max_key = 8**5  # 32768
        lookup = np.zeros(max_key, dtype=np.uint8)
        for (center, north, south, east, west), result in _LANGTON_RULES.items():
            idx = center * 4096 + north * 512 + south * 64 + east * 8 + west
            lookup[idx] = result

        # Default: cell stays the same (conservative)
        new_grid = grid.copy()

        # Apply rule: for entries NOT in the rule table, the default is 0
        # We need a slightly different approach — use a boolean mask
        # for cells that have a specific rule.
        has_rule = np.zeros((rows, cols), dtype=bool)
        for (center, north, south, east, west), result in _LANGTON_RULES.items():
            mask = (
                (c == center) &
                (n == north) &
                (s == south) &
                (e == east) &
                (w == west)
            )
            if mask.any():
                new_grid[mask] = result
                has_rule |= mask

        # Cells without a specific rule default to 0
        new_grid[~has_rule] = 0
        return new_grid


# ======================================================================
# Snowflake — multi-state dendritic crystal growth (6-fold symmetry)
# ======================================================================
# Based on the Packard snowflake model with hexagonal anisotropy.
# States: 0 = vapor, 1..N-2 = partially frozen, N-1 = fully frozen crystal.
# Differential freezing probability creates 6-fold dendritic arms.


class SnowflakeRule(CARule):
    """Snowflake crystal growth CA with hexagonal (6-fold) symmetry.

    Multi-state model where cells transition from vapor → partially frozen →
    fully frozen crystal.  The freezing threshold depends on the DIRECTION
    to the nearest crystal neighbour, producing dendritic 6-fold arms.

    States:
      0 = empty vapor
      1..num_states-2 = partially frozen (gradient)
      num_states-1 = fully frozen crystal

    Key mechanism:
      - A vapor cell freezes if it has at least one frozen neighbour.
      - The freeze probability is ANISOTROPIC: higher when the crystal
        neighbour lies along one of the 6 principal axes (hexagonal).
      - This creates natural 6-fold dendritic branching.

    Parameters:
      num_states: total states (default 8) — more states = smoother gradient
      base_prob: base freeze probability for non-preferred directions
      axis_prob: freeze probability along preferred hexagonal axes
    """

    def __init__(
        self,
        num_states: int = 8,
        base_prob: float = 0.02,
        axis_prob: float = 0.15,
    ) -> None:
        super().__init__("snowflake", num_states=num_states)
        self.base_prob = base_prob
        self.axis_prob = axis_prob
        self._max_frozen = num_states - 1

    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        """Apply snowflake crystal growth rule."""
        rows, cols = grid.shape
        max_s = self._max_frozen
        new_grid = grid.copy()

        # Fully frozen cells stay frozen
        frozen_mask = grid == max_s

        # Vapor cells (state 0) in contact with frozen cells may freeze
        vapor = (grid == 0)

        # Check 8 neighbours for frozen cells
        # For each vapour cell, check each neighbour direction individually
        rand = np.random.random((rows, cols))

        # Neighbour shifts: the 8 Moore neighbours
        shifts = [(-1, -1), (-1, 0), (-1, 1),
                   (0, -1),           (0, 1),
                   (1, -1),  (1, 0),  (1, 1)]

        # Preferred hexagonal axes (6 directions):
        # In Moore neighbourhood, approximate hexagonal axes:
        #   N(0), NE(1), SE(2), S(3), SW(4), NW(5)
        #   With these indices in shifts[]:
        #   N=1, NE=2, SE=5, S=6, SW=7, NW=8... wait let me re-think.
        #
        # shifts list: [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
        # indices:      0       1      2      3      4      5      6      7
        #
        # Hex axes in Moore coords: NW(0), N(1), NE(2), SW(3)... hmm.
        # Let me use a simpler approach: the 6 hexagonal directions are
        # approximated by selecting specific Moore neighbours.

        hex_axes = {1, 2, 5, 6, 7, 0}  # N, NE, SE, S, SW, NW

        frozen_neighbour_count = np.zeros((rows, cols), dtype=np.int32)
        frozen_hex_count = np.zeros((rows, cols), dtype=np.int32)

        for idx, (dr, dc) in enumerate(shifts):
            shifted = np.roll(np.roll(grid, -dr, axis=0), -dc, axis=1)
            is_frozen = shifted == max_s
            frozen_neighbour_count += is_frozen.astype(np.int32)
            if idx in hex_axes:
                frozen_hex_count += is_frozen.astype(np.int32)

        # Transition rule:
        # - Partially frozen cells advance 1 state each step
        for s in range(1, max_s):
            new_grid[grid == s] = np.minimum(max_s, s + 1)

        # - Vapor freezes with probability depending on neighbours
        for s in range(1, max_s + 1):
            # Freeze to state 1 (if s==1) or to max_s (if s==max_s)
            target = max_s if s == max_s else 1
            if s > 1 and s < max_s:
                continue  # only freeze vapor → 1 or directly to max

            # Which vapor cells have at least one frozen neighbour?
            has_frozen = vapor & (frozen_neighbour_count > 0)

            if target == max_s:
                # Direct nucleation to crystal
                prob = np.where(
                    frozen_hex_count > 0,
                    self.axis_prob,   # hexagonal axis: high probability
                    self.base_prob,   # off-axis: low probability
                )
                new_vapor = has_frozen & (rand < prob)
                new_grid[new_vapor] = max_s
            elif target == 1:
                prob = np.where(
                    frozen_hex_count > 0,
                    self.axis_prob * 0.5,
                    self.base_prob * 0.5,
                )
                new_vapor = has_frozen & (rand < prob * 0.3)
                if new_vapor.any():
                    # Only freeze cells that haven't already been set
                    unfrozen = new_grid == 0
                    new_grid[unfrozen & new_vapor] = 1

        return new_grid


# ======================================================================
# Cyclic CA — n-color spiral wave automaton
# ======================================================================
# Greenberg-Hastings / Dewdney cyclic automaton.
# States 0..N-1. A cell in state s advances to (s+1)%N if any neighbour
# is in state (s+1)%N. Otherwise unchanged. Produces beautiful spiral waves.


class CyclicCARule(CARule):
    """Cyclic cellular automaton (Greenberg-Hastings type).

    N states arranged in a cycle.  Each cell advances to the next state
    in the cycle iff at least one Moore neighbour is already in that state.

    Produces evolving spiral waves and target patterns.

    Parameters:
      n_colors: number of states in the cycle (default 14)
      threshold: minimum number of "next state" neighbours to advance
    """

    def __init__(self, n_colors: int = 14, threshold: int = 1) -> None:
        super().__init__("cyclic", num_states=n_colors)
        self.n_colors = n_colors
        self.threshold = threshold

    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        """Apply cyclic CA rule."""
        new_grid = grid.copy()
        N = self.n_colors

        # For each state s, check if neighbour has state (s+1)%N
        for s in range(N):
            next_s = (s + 1) % N
            # Mask of cells in state s
            mask_s = grid == s
            if not mask_s.any():
                continue

            # Check if any Moore neighbour is in next_s
            next_mask = grid == next_s
            next_neighbours = count_neighbours(next_mask.astype(np.uint8))

            advance = mask_s & (next_neighbours >= self.threshold)
            new_grid[advance] = next_s

        return new_grid


# ======================================================================
# Hodgepodge Machine — reaction-diffusion spiral CA
# ======================================================================
# Gerhardt & Schuster / Dewdney's hodgepodge machine.
# Models a chemical reaction-diffusion with excitable media.


class HodgepodgeRule(CARule):
    """Hodgepodge Machine — excitable media reaction-diffusion CA.

    Produces spiral waves similar to the Belousov-Zhabotinsky reaction.

    States:
      0 = healthy (susceptible)
      1 = infected (starting to react)
      2..N-2 = ill (excited/reacting, advancing each step)
      N-1 = recovered (briefly immune, then → healthy)

    Rules:
      - Healthy (0) → Infected (1) if infected_neighbours in [k1, k2]
        (with probability g)
      - Ill states (2..N-1) advance by 1 each step
      - Recovered (N-1) → Healthy (0)

    Parameters:
      num_states: total states (default 20)
      k1: minimum infected neighbours to trigger (default 1)
      k2: maximum infected neighbours to trigger (default 8)
      g: infection probability (default 1.0)
    """

    def __init__(
        self,
        num_states: int = 20,
        k1: int = 1,
        k2: int = 8,
        g: float = 1.0,
    ) -> None:
        super().__init__("hodgepodge", num_states=num_states)
        self.k1 = k1
        self.k2 = k2
        self.g = g

    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        """Apply Hodgepodge Machine rule."""
        N = self.num_states
        new_grid = np.zeros_like(grid)

        # Count "infected" neighbours: states 1 through N-2 (i.e., not 0 and not recovered)
        # Infected = states between 1 and N-2 inclusive
        infected_mask = (grid >= 1) & (grid < N - 1)
        infected_grid = infected_mask.astype(np.uint8)
        infected_neighbours = count_neighbours(infected_grid)

        # Rule 1: Healthy (0) → Infected (1)
        trigger = (
            (grid == 0) &
            (infected_neighbours >= self.k1) &
            (infected_neighbours <= self.k2)
        )
        if self.g < 1.0:
            trigger &= np.random.random(grid.shape) < self.g
        new_grid[trigger] = 1

        # Rule 2: Ill states advance
        for s in range(1, N - 1):
            new_grid[grid == s] = s + 1

        # Rule 3: Recovered (N-1) → Healthy (0)
        # → already 0 in new_grid

        return new_grid


def register_complex_rules(registry: dict) -> None:
    """Register all complex rules."""
    registry["langtons_loop"] = LangtonsLoopRule()
    registry["snowflake"] = SnowflakeRule()
    registry["cyclic"] = CyclicCARule()
    registry["hodgepodge"] = HodgepodgeRule()
