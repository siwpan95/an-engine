"""Rule base classes and neighbour-counting utilities.

Provides:
  - CARule (abstract base)
  - OuterTotalisticRule (B/S notation for 2-state CA)
  - count_neighbours (Moore neighbourhood, 8-connected, via convolve2d or roll)
  - count_von_neumann_neighbours (von Neumann, 4-connected)
"""

from __future__ import annotations

import abc
from typing import Optional

import numpy as np
from numpy.typing import NDArray

# ---------------------------------------------------------------------------
# Try scipy.signal.convolve2d for performance; fall back to np.roll
# ---------------------------------------------------------------------------
try:
    from scipy.signal import convolve2d as _convolve2d

    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

# Pre-build convolution kernel for 8-connected Moore neighbourhood
_MOORE_KERNEL: NDArray[np.int32] = np.array([
    [1, 1, 1],
    [1, 0, 1],
    [1, 1, 1],
], dtype=np.int32)

# Pre-built von Neumann kernel (cardinal directions only)
_VON_NEUMANN_KERNEL: NDArray[np.int32] = np.array([
    [0, 1, 0],
    [1, 0, 1],
    [0, 1, 0],
], dtype=np.int32)

# ---------------------------------------------------------------------------
# Neighbour-counting
# ---------------------------------------------------------------------------


def count_neighbours(grid: NDArray[np.uint8]) -> NDArray[np.int32]:
    """Count 8-connected Moore neighbours for every cell.

    Uses scipy.signal.convolve2d when available (faster), otherwise
    falls back to numpy.roll.  Both use toroidal (wrap) boundaries.
    """
    if _HAS_SCIPY:
        return _convolve2d(
            grid.astype(np.int32, copy=False),
            _MOORE_KERNEL,
            mode="same",
            boundary="wrap",
        ).astype(np.int32)
    else:
        # Fallback: vectorized np.roll
        result = np.zeros_like(grid, dtype=np.int32)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                result += np.roll(np.roll(grid, -dr, axis=0), -dc, axis=1)
        return result


def count_von_neumann_neighbours(grid: NDArray[np.uint8]) -> NDArray[np.int32]:
    """Count 4-connected von Neumann neighbours (N, S, E, W) for every cell.

    Uses convolve2d or roll with toroidal (wrap) boundaries.
    """
    if _HAS_SCIPY:
        return _convolve2d(
            grid.astype(np.int32, copy=False),
            _VON_NEUMANN_KERNEL,
            mode="same",
            boundary="wrap",
        ).astype(np.int32)
    else:
        result = np.zeros_like(grid, dtype=np.int32)
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            result += np.roll(np.roll(grid, -dr, axis=0), -dc, axis=1)
        return result


# ---------------------------------------------------------------------------
# Rule base classes
# ---------------------------------------------------------------------------


class CARule(abc.ABC):
    """Abstract base class for all CA rules."""

    def __init__(self, name: str, num_states: int = 2) -> None:
        self.name = name
        self.num_states = num_states

    @abc.abstractmethod
    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        """Compute the next generation of the grid.

        Args:
            grid: Current state grid (uint8)
            neighbours: Pre-computed neighbour counts (optional)

        Returns:
            New state grid (uint8)
        """
        ...


class OuterTotalisticRule(CARule):
    """Traditional 2-state outer-totalistic CA rule (Conway-like B/S notation).

    Rules are defined by two sets:
    - born: neighbour counts that cause a dead cell to become alive
    - survive: neighbour counts that keep a live cell alive
    """

    def __init__(self, name: str, born: set[int], survive: set[int]) -> None:
        super().__init__(name, num_states=2)
        self.born = born
        self.survive = survive
        self._born_arr = np.array(sorted(born), dtype=np.int32)
        self._survive_arr = np.array(sorted(survive), dtype=np.int32)

    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        """Apply outer-totalistic rule."""
        if neighbours is None:
            neighbours = count_neighbours(grid)

        born_mask = np.isin(neighbours, self._born_arr) & (grid == 0)
        survive_mask = np.isin(neighbours, self._survive_arr) & (grid == 1)
        return (born_mask | survive_mask).astype(np.uint8)

    def __repr__(self) -> str:
        b = "".join(str(n) for n in sorted(self.born))
        s = "".join(str(n) for n in sorted(self.survive))
        return f"OuterTotalisticRule({self.name!r}, B{b}/S{s})"
