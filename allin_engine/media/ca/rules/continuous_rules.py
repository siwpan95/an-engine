"""Continuous cellular automaton rules with float-based state.

Includes:
  - Gray-Scott Reaction-Diffusion (spots, stripes, maze patterns)
  - Lenia (continuous Game of Life variant, organic lifeforms)
  - Larger than Life (extended-radius neighborhood)
  - Wolfram Elementary 1D CA (rules 0-255)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from numpy.typing import NDArray

from allin_engine.media.ca.rules.base import CARule, count_neighbours

# Try scipy for convolution
try:
    from scipy.signal import convolve2d as _convolve2d
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


# ======================================================================
# Gray-Scott Reaction-Diffusion
# ======================================================================
# Classic Turing pattern generator.
# ∂u/∂t = Du∇²u − uv² + f(1−u)
# ∂v/∂t = Dv∇²v + uv² − (f+k)v
#
# Parameter presets produce different pattern types:
#   "spots"     f=0.035, k=0.065  — stationary dots
#   "stripes"   f=0.030, k=0.062  — labyrinthine stripes
#   "maze"      f=0.025, k=0.060  — maze / mitosis
#   "waves"     f=0.040, k=0.060  — traveling waves
#   "pulsating" f=0.050, k=0.065  — breathing spots
#   "chaos"     f=0.020, k=0.055  — turbulent chaos
#   "bubbles"   f=0.012, k=0.050  — large bubbles

_GRAY_SCOTT_PRESETS: dict[str, tuple[float, float]] = {
    "spots":     (0.035, 0.065),
    "stripes":   (0.030, 0.062),
    "maze":      (0.025, 0.060),
    "waves":     (0.040, 0.060),
    "pulsating": (0.050, 0.065),
    "chaos":     (0.020, 0.055),
    "bubbles":   (0.012, 0.050),
    "tendrils":  (0.027, 0.058),
    "solitons":  (0.030, 0.057),
}


def _laplacian(field: NDArray[np.float32]) -> NDArray[np.float32]:
    """Compute discrete Laplacian (∇²) using 5-point stencil, toroidal."""
    if _HAS_SCIPY:
        kernel = np.array([
            [0.05, 0.2,  0.05],
            [0.2, -1.0,  0.2],
            [0.05, 0.2,  0.05],
        ], dtype=np.float32)
        return _convolve2d(field, kernel, mode="same", boundary="wrap")
    else:
        # Manual roll-based Laplacian
        lap = np.zeros_like(field)
        for dr, dc, w in [(-1, 0, 0.2), (1, 0, 0.2), (0, -1, 0.2),
                           (0, 1, 0.2), (-1, -1, 0.05), (-1, 1, 0.05),
                           (1, -1, 0.05), (1, 1, 0.05)]:
            shifted = np.roll(np.roll(field, -dr, axis=0), -dc, axis=1)
            lap += w * (shifted - field)
        return lap


class GrayScottRule(CARule):
    """Gray-Scott Reaction-Diffusion model.

    Produces biological-looking Turing patterns: spots, stripes, maze,
    bubbles, and spirals depending on the feed (f) and kill (k) rates.

    This rule manages its own float32 U and V fields internally.
    The grid output is a uint8 visualization.

    Presets: spots, stripes, maze, waves, pulsating, chaos, bubbles,
             tendrils, solitons
    """

    def __init__(
        self,
        preset: str = "spots",
        Du: float = 0.16,
        Dv: float = 0.08,
        dt: float = 1.0,
    ) -> None:
        super().__init__("gray_scott", num_states=256)
        f, k = _GRAY_SCOTT_PRESETS.get(preset, (0.035, 0.065))
        self.preset = preset
        self.f = f
        self.k = k
        self.Du = Du
        self.Dv = Dv
        self.dt = dt
        self._U: NDArray[np.float32] | None = None
        self._V: NDArray[np.float32] | None = None
        self._initialized = False

    def _ensure_state(self, shape: tuple[int, int]) -> None:
        """Initialize U, V fields if not already set."""
        if not self._initialized or self._U is None or self._U.shape != shape:
            rows, cols = shape
            rng = np.random.default_rng()
            self._U = np.ones((rows, cols), dtype=np.float32)
            self._V = np.zeros((rows, cols), dtype=np.float32)
            # Seed a central square of V
            r_start = rows // 2 - rows // 8
            r_end = rows // 2 + rows // 8
            c_start = cols // 2 - cols // 8
            c_end = cols // 2 + cols // 8
            self._V[r_start:r_end, c_start:c_end] = rng.random(
                (r_end - r_start, c_end - c_start)
            ).astype(np.float32) * 0.5 + 0.25
            # Perturb U in the seed region
            self._U[r_start:r_end, c_start:c_end] = rng.random(
                (r_end - r_start, c_end - c_start)
            ).astype(np.float32) * 0.2 + 0.3
            self._initialized = True

    def reset(self, shape: tuple[int, int]) -> None:
        """Force re-initialization next step."""
        self._initialized = False

    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        """Advance Gray-Scott by one timestep, return uint8 visualization."""
        self._ensure_state(grid.shape)
        assert self._U is not None and self._V is not None

        # Reaction-diffusion update
        lap_u = _laplacian(self._U)
        lap_v = _laplacian(self._V)

        du = (self.Du * lap_u - self._U * self._V * self._V
              + self.f * (1.0 - self._U)) * self.dt
        dv = (self.Dv * lap_v + self._U * self._V * self._V
              - (self.f + self.k) * self._V) * self.dt

        self._U += du
        self._V += dv

        # Clip to valid range
        np.clip(self._U, 0.0, 1.0, out=self._U)
        np.clip(self._V, 0.0, 1.0, out=self._V)

        # Quantize U field to uint8 for visualization
        return (self._U * 255).astype(np.uint8)

    @property
    def u_field(self) -> NDArray[np.float32] | None:
        """Access the U (activator) field for custom rendering."""
        return self._U

    @property
    def v_field(self) -> NDArray[np.float32] | None:
        """Access the V (inhibitor) field for custom rendering."""
        return self._V

    @property
    def has_float_state(self) -> bool:
        """Indicate this rule manages its own float state."""
        return True


# ======================================================================
# Lenia — Continuous Cellular Automata
# ======================================================================
# Generalized Conway-like CA with continuous space, time, and states.
# Uses a kernel convolution and a growth function G(x) to update.
#
# A = conv(grid, kernel)    — "potential"
# grid += G(A) * dt          — growth
# clip to [0, 1]
#
# The kernel is a ring-shaped bump function.
# G(x) = 2 * exp(-(x-μ)²/(2σ²)) - 1, clipped to [-1, 1]


def _build_lenia_kernel(R: int, mu: float, sigma: float) -> NDArray[np.float32]:
    """Build a Lenia ring-shaped kernel of radius R."""
    size = 2 * R + 1
    kernel = np.zeros((size, size), dtype=np.float32)
    center = R
    for dy in range(size):
        for dx in range(size):
            dist = np.sqrt((dy - center)**2 + (dx - center)**2) / R
            if dist <= 1.0:
                # Ring bump: peak at dist=mu, width sigma
                kernel[dy, dx] = np.exp(-((dist - mu)**2) / (2 * sigma**2))
    # Normalize
    s = kernel.sum()
    if s > 0:
        kernel /= s
    return kernel


class LeniaRule(CARule):
    """Lenia — continuous cellular automaton with organic lifeforms.

    Extends Conway's Game of Life to continuous domains with:
    - Continuous states in [0, 1]
    - Smooth ring-shaped kernel for potential computation
    - Growth function for birth/death transitions

    Produces gliders, spaceships, and organic-looking creatures that
    smoothly flow across the grid.

    Parameters:
      kernel_radius: radius of the convolution kernel (default 13)
      mu: center of the growth ring (default 0.15)
      sigma: width of the growth ring (default 0.015)
      dt: time step (default 0.1)
      species: "orbium" (classic orb), "hydro" (flowing), "parasite" (swarm)
    """

    _SPECIES_PARAMS = {
        "orbium":  (10, 0.15, 0.015, 0.1),
        "hydro":   (20, 0.12, 0.018, 0.15),
        "parasite":(15, 0.18, 0.012, 0.08),
        "frother": (8,  0.20, 0.014, 0.12),
    }

    def __init__(
        self,
        kernel_radius: int = 13,
        mu: float = 0.15,
        sigma: float = 0.015,
        dt: float = 0.1,
        species: str = "orbium",
    ) -> None:
        super().__init__("lenia", num_states=256)
        if species in self._SPECIES_PARAMS:
            kernel_radius, mu, sigma, dt = self._SPECIES_PARAMS[species]
        self.species = species
        self.kernel_radius = kernel_radius
        self.mu = mu
        self.sigma = sigma
        self.dt = dt
        self._kernel: NDArray[np.float32] | None = None
        self._field: NDArray[np.float32] | None = None
        self._initialized = False

    def _ensure_state(self, shape: tuple[int, int]) -> None:
        """Initialize kernel and field."""
        if self._kernel is None:
            self._kernel = _build_lenia_kernel(
                self.kernel_radius, self.mu, self.sigma,
            )
        if not self._initialized or self._field is None or self._field.shape != shape:
            rng = np.random.default_rng()
            rows, cols = shape
            self._field = np.zeros((rows, cols), dtype=np.float32)
            # Seed a doughnut-shaped initial lifeform
            cy, cx = rows // 2, cols // 2
            R = min(rows, cols) // 6
            Y, X = np.ogrid[:rows, :cols]
            dist = np.sqrt((Y - cy)**2 + (X - cx)**2)
            # Ring between R/2 and R
            ring = (dist >= R / 2) & (dist <= R)
            self._field[ring] = rng.random(ring.sum()).astype(np.float32) * 0.8 + 0.2
            self._initialized = True

    def reset(self, shape: tuple[int, int]) -> None:
        """Force re-initialization next step."""
        self._initialized = False
        self._kernel = None

    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        """Advance Lenia by one timestep, return uint8 visualization."""
        self._ensure_state(grid.shape)
        assert self._field is not None and self._kernel is not None

        # Convolve field with kernel to get potential
        if _HAS_SCIPY:
            potential = _convolve2d(
                self._field, self._kernel, mode="same", boundary="wrap",
            )
        else:
            # Manual convolution via FFT or direct... use sum of rolls
            kh, kw = self._kernel.shape
            potential = np.zeros_like(self._field)
            R = kh // 2
            for dy in range(kh):
                for dx in range(kw):
                    k = self._kernel[dy, dx]
                    if k != 0:
                        potential += k * np.roll(
                            np.roll(self._field, dy - R, axis=0), dx - R, axis=1,
                        )

        # Growth function: G(x) = 2*exp(-(x-μ)²/(2σ²)) - 1
        growth = 2.0 * np.exp(
            -((potential - self.mu) ** 2) / (2 * self.sigma ** 2)
        ) - 1.0

        # Update field
        self._field += growth * self.dt
        np.clip(self._field, 0.0, 1.0, out=self._field)

        # Return quantized visualization
        return (self._field * 255).astype(np.uint8)

    @property
    def field(self) -> NDArray[np.float32] | None:
        """Access the continuous field for custom rendering."""
        return self._field

    @property
    def has_float_state(self) -> bool:
        """Indicate this rule manages its own float state."""
        return True


# ======================================================================
# Larger than Life — extended-radius neighborhood
# ======================================================================
# Notation: Rr,Cc,Mm,Ss_min..s_max,Bb_min..b_max,Nn
# R = range, C = cell states (always 2 here), M = neighborhood type (Moore=0, Circle=1)
# S = survival range, B = birth range


class LargerThanLifeRule(CARule):
    """Larger than Life — CA with extended neighborhood radius.

    Extends outer-totalistic rules to arbitrarily large neighborhoods.
    Creates macro-scale behavior: large gliders, expanding bugs, etc.

    Parameters:
      radius: neighborhood radius (default 5)
      born_min/max: birth neighbor count range
      survive_min/max: survival neighbor count range
      preset: one of "bugs", "bugs2", "brain", "moving_sand"

    Presets:
      bugs (R5):   B34..45/S34..58  — Large bug-like gliders
      bugs2 (R3):  B21..31/S10..21  — Smaller gliders
      brain (R4):  B33..45/S32..62  — Brain-like structures
      sand (R2):   B10..16/S10..16  — Flowing sand texture
      cities (R3): B18..26/S18..26  — City-like blocks
      worms (R7):  B74..87/S70..98  — Worm-like creatures
    """

    _PRESETS = {
        "bugs":   (5, 34, 45, 34, 58),
        "bugs2":  (3, 21, 31, 10, 21),
        "brain":  (4, 33, 45, 32, 62),
        "sand":   (2, 10, 16, 10, 16),
        "cities": (3, 18, 26, 18, 26),
        "worms":  (7, 74, 87, 70, 98),
        "bubbles":(4, 20, 28, 40, 60),
    }

    def __init__(
        self,
        radius: int = 5,
        born_min: int = 34,
        born_max: int = 45,
        survive_min: int = 34,
        survive_max: int = 58,
        preset: str = "bugs",
    ) -> None:
        super().__init__("larger_than_life", num_states=2)
        if preset in self._PRESETS:
            radius, born_min, born_max, survive_min, survive_max = \
                self._PRESETS[preset]
        self.radius = radius
        self.born_min = born_min
        self.born_max = born_max
        self.survive_min = survive_min
        self.survive_max = survive_max
        self.preset = preset

        # Pre-build circular mask
        self._mask = self._build_mask(radius)

    def _build_mask(self, R: int) -> NDArray[np.bool_]:
        """Build a circular boolean mask of radius R (true = in neighborhood)."""
        size = 2 * R + 1
        Y, X = np.ogrid[-R:R + 1, -R:R + 1]
        dist = np.sqrt(Y**2 + X**2)
        mask = (dist <= R) & ~(dist == 0)
        return mask

    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        """Apply Larger than Life rule with circular neighborhood."""
        # Count neighbours within radius using convolution or roll
        R = self.radius
        if _HAS_SCIPY and R <= 20:
            kernel = self._mask.astype(np.int32)
            total = _convolve2d(
                grid.astype(np.int32, copy=False),
                kernel,
                mode="same",
                boundary="wrap",
            ).astype(np.int32)
        else:
            total = np.zeros_like(grid, dtype=np.int32)
            size = 2 * R + 1
            for dy in range(size):
                for dx in range(size):
                    if self._mask[dy, dx]:
                        total += np.roll(
                            np.roll(grid, dy - R, axis=0), dx - R, axis=1,
                        ).astype(np.int32)

        born_mask = (
            (grid == 0) &
            (total >= self.born_min) &
            (total <= self.born_max)
        )
        survive_mask = (
            (grid == 1) &
            (total >= self.survive_min) &
            (total <= self.survive_max)
        )
        return (born_mask | survive_mask).astype(np.uint8)


# ======================================================================
# Wolfram Elementary 1D Cellular Automaton
# ======================================================================
# 256 elementary rules (0-255). Each cell's next state depends on
# its own state and its two neighbors (3-bit pattern → 1-bit output).
#
# Famous rules:
#   Rule 30  — chaotic, used for random number generation
#   Rule 90  — Sierpinski triangle
#   Rule 110 — Turing complete
#   Rule 184 — traffic flow model
#   Rule 54  — complex, glider-like structures


class Elementary1DRule(CARule):
    """Wolfram's Elementary 1D Cellular Automaton.

    The grid is interpreted as a stack of rows (history).
    Each step computes the next row based on the previous row.

    States: 0 or 1 (the rule output is always 2-state).

    Rules 0-255. The rule number's binary representation defines
    the output for each 3-bit neighborhood pattern.

    Parameters:
      rule_number: Wolfram rule 0-255 (default 30)
    """

    _FAMOUS = {
        "rule30": 30, "rule90": 90, "rule110": 110,
        "rule184": 184, "rule54": 54, "rule22": 22,
        "rule126": 126, "rule150": 150, "rule45": 45,
        "rule73": 73, "rule105": 105,
    }

    def __init__(self, rule_number: int = 30) -> None:
        super().__init__("elementary_1d", num_states=2)
        self.rule_number = rule_number % 256
        # Build lookup: pattern (l,c,r) → bit
        # pattern index = l*4 + c*2 + r
        self._lookup = np.zeros(8, dtype=np.uint8)
        for i in range(8):
            self._lookup[i] = (self.rule_number >> i) & 1

    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        """Compute the next row of the 1D CA.

        The grid is treated as a history buffer:
        - Row 0 = newest generation (computed bottom-up)
        - Each step: shift all rows down (away from top),
                     compute new row 0 from current row 0,
                     insert new row 0 at top.
        """
        rows, cols = grid.shape
        # Shift all rows DOWN by 1 (row N-1 wraps to row 0)
        new_grid = np.roll(grid, 1, axis=0)

        # Compute new top row from current top row
        current_row = grid[0, :]
        left = np.roll(current_row, 1)
        right = np.roll(current_row, -1)

        # Encode pattern: left*4 + center*2 + right
        pattern = (left.astype(np.int32) * 4 +
                    current_row.astype(np.int32) * 2 +
                    right.astype(np.int32))
        new_row = self._lookup[pattern]

        new_grid[0, :] = new_row
        return new_grid

    def init_grid(self, rows: int, cols: int) -> NDArray[np.uint8]:
        """Create a fresh grid with a single cell in the top row."""
        g = np.zeros((rows, cols), dtype=np.uint8)
        g[0, cols // 2] = 1
        return g


# ======================================================================
# SmoothLife — Continuous Game of Life
# ======================================================================
# Extends Conway's Game of Life to continuous domains.
# Uses smooth Gaussian-weighted neighborhoods and sigmoid transitions.
#
# Field f in [0, 1].
# inner = weighted average in inner disk (radius r_i)
# outer = weighted average in outer ring (radius r_o)
# birth = sigmoid((outer - b1) * sharpness) when inner < 0.5
# survival = sigmoid((outer - d1) * sharpness) when inner >= 0.5
# transition = birth if inner < 0.5 else survival
# f_new = f + dt * (2 * transition - 1 - f)


def _build_gaussian_kernel(R: int, inner: bool = False) -> NDArray[np.float32]:
    """Build a Gaussian-weighted disk (inner) or ring (outer) kernel."""
    size = 2 * R + 1
    kernel = np.zeros((size, size), dtype=np.float32)
    center = R
    r_inner = R * 0.3
    r_outer = float(R)
    for dy in range(size):
        for dx in range(size):
            dist = np.sqrt((dy - center)**2 + (dx - center)**2)
            if inner:
                if dist <= r_inner:
                    kernel[dy, dx] = np.exp(-(dist / max(r_inner, 1))**2 * 2)
            else:
                if r_inner < dist <= r_outer:
                    # Ring: Gaussian centered at midpoint
                    mid = (r_inner + r_outer) / 2
                    width = (r_outer - r_inner) / 2
                    kernel[dy, dx] = np.exp(-((dist - mid) / max(width, 1))**2 * 2)
    s = kernel.sum()
    if s > 0:
        kernel /= s
    return kernel


class SmoothLifeRule(CARule):
    """SmoothLife — continuous cellular automaton by Stephan Rafler.

    Extends Conway's Game of Life to continuous state space [0, 1]
    with smooth Gaussian neighborhoods and sigmoid transition functions.

    Produces smooth, flowing patterns: gliders that morph and merge,
    organic structures that breathe and evolve.

    Parameters:
      radius: outer neighborhood radius (default 5)
      b1: birth threshold lower (default 0.257)
      b2: birth threshold upper (default 0.336)
      d1: death/survival threshold lower (default 0.365)
      d2: death/survival threshold upper (default 0.549)
      sharpness: sigmoid steepness (default 0.028)
      dt: time step (default 0.1)

    Reference:
      Rafler, S. (2011). "Generalization of Conway's Game of Life
      to a continuous domain - SmoothLife."
    """

    def __init__(
        self,
        radius: int = 5,
        b1: float = 0.257,
        b2: float = 0.336,
        d1: float = 0.365,
        d2: float = 0.549,
        sharpness: float = 0.028,
        dt: float = 0.1,
    ) -> None:
        super().__init__("smooth_life", num_states=256)
        self.radius = radius
        self.b1 = b1
        self.b2 = b2
        self.d1 = d1
        self.d2 = d2
        self.sharpness = sharpness
        self.dt = dt
        self._kernel_inner: NDArray[np.float32] | None = None
        self._kernel_outer: NDArray[np.float32] | None = None
        self._field: NDArray[np.float32] | None = None
        self._initialized = False

    def _ensure_state(self, shape: tuple[int, int]) -> None:
        """Initialize kernels and field."""
        if self._kernel_inner is None:
            self._kernel_inner = _build_gaussian_kernel(self.radius, inner=True)
            self._kernel_outer = _build_gaussian_kernel(self.radius, inner=False)
        if not self._initialized or self._field is None or self._field.shape != shape:
            rng = np.random.default_rng()
            rows, cols = shape
            self._field = np.zeros((rows, cols), dtype=np.float32)
            # Seed with random noise in central region
            cy, cx = rows // 2, cols // 2
            r = min(rows, cols) // 4
            self._field[
                cy - r:cy + r, cx - r:cx + r
            ] = rng.random((2 * r, 2 * r)).astype(np.float32) * 0.8 + 0.1
            self._initialized = True

    def reset(self, shape: tuple[int, int]) -> None:
        """Force re-initialization next step."""
        self._initialized = False
        self._kernel_inner = None
        self._kernel_outer = None

    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        """Advance SmoothLife by one timestep, return uint8 visualization."""
        self._ensure_state(grid.shape)
        assert self._field is not None
        assert self._kernel_inner is not None and self._kernel_outer is not None

        if _HAS_SCIPY:
            inner_avg = _convolve2d(
                self._field, self._kernel_inner, mode="same", boundary="wrap",
            )
            outer_avg = _convolve2d(
                self._field, self._kernel_outer, mode="same", boundary="wrap",
            )
        else:
            # Manual convolution via rolls
            kh, kw = self._kernel_inner.shape
            R = kh // 2
            inner_avg = np.zeros_like(self._field)
            for dy in range(kh):
                for dx in range(kw):
                    k = self._kernel_inner[dy, dx]
                    if k != 0:
                        inner_avg += k * np.roll(
                            np.roll(self._field, dy - R, axis=0), dx - R, axis=1,
                        )
            kh, kw = self._kernel_outer.shape
            R = kh // 2
            outer_avg = np.zeros_like(self._field)
            for dy in range(kh):
                for dx in range(kw):
                    k = self._kernel_outer[dy, dx]
                    if k != 0:
                        outer_avg += k * np.roll(
                            np.roll(self._field, dy - R, axis=0), dx - R, axis=1,
                        )

        # Sigmoid transition function
        s = self.sharpness

        # Birth/survival depends on inner state
        # When inner < 0.5: birth zone — cell tends toward 1 if outer in [b1, b2]
        # When inner >= 0.5: survival zone — cell tends toward 1 if outer in [d1, d2]
        birth = 1.0 / (1.0 + np.exp(-(outer_avg - self.b1) / s)) * \
                (1.0 / (1.0 + np.exp(-(self.b2 - outer_avg) / s)))
        survival = 1.0 / (1.0 + np.exp(-(outer_avg - self.d1) / s)) * \
                   (1.0 / (1.0 + np.exp(-(self.d2 - outer_avg) / s)))

        # Smooth transition based on current inner value
        aliveness = 1.0 / (1.0 + np.exp(-(inner_avg - 0.5) / 0.15))
        transition = birth * (1.0 - aliveness) + survival * aliveness

        # Update field: f += dt * (2*transition - 1 - f)
        self._field += self.dt * (2.0 * transition - 1.0 - self._field)
        np.clip(self._field, 0.0, 1.0, out=self._field)

        return (self._field * 255).astype(np.uint8)

    @property
    def field(self) -> NDArray[np.float32] | None:
        """Access the continuous field for custom rendering."""
        return self._field

    @property
    def has_float_state(self) -> bool:
        """Indicate this rule manages its own float state."""
        return True


# ======================================================================
# Belousov-Zhabotinsky Reaction — spiral wave CA
# ======================================================================
# A discrete CA model of the BZ chemical reaction.
# States 0..N-1 represent chemical concentrations.
# Produces beautiful spiral wave patterns similar to the real reaction.
#
# Rules:
#   - State 0 (resting): advance to excited if weighted neighbour sum >= threshold
#   - States 1..N-2 (excited/refractory): advance by 1 each step
#   - State N-1 (recovered): return to 0


# Pre-build float Moore kernel for BZ reaction convolution
_MOORE_KERNEL_FLOAT: NDArray[np.float32] = np.array([
    [1, 1, 1],
    [1, 0, 1],
    [1, 1, 1],
], dtype=np.float32)

class BZReactionRule(CARule):
    """Belousov-Zhabotinsky reaction as a discrete cellular automaton.

    Models the BZ chemical reaction which produces striking spiral
    wave patterns.  Each cell cycles through N states representing
    chemical concentrations.

    States:
      0 = resting (susceptible to excitation)
      1 = excited (triggered by neighbours)
      2..N-2 = refractory (gradually recovering)
      N-1 = recovered (about to return to resting)

    Rules:
      - Resting (0) -> excited (1) if neighbour activation >= threshold
      - Excited/refractory states advance by 1 each step
      - Recovered (N-1) -> resting (0)

    Parameters:
      num_states: total states (default 16, more = smoother gradients)
      threshold: activation threshold for excitation (default 10)
      weight_excited: weight of excited neighbours (default 1.0)
      weight_refractory: weight of refractory neighbours (negative, default -0.5)
    """

    def __init__(
        self,
        num_states: int = 16,
        threshold: float = 10.0,
        weight_excited: float = 1.0,
        weight_refractory: float = -0.5,
    ) -> None:
        super().__init__("bz_reaction", num_states=num_states)
        self.threshold = threshold
        self.weight_excited = weight_excited
        self.weight_refractory = weight_refractory
        self._excited_max = num_states // 3  # states 1..excited_max are "excited"

    def step(
        self,
        grid: NDArray[np.uint8],
        neighbours: Optional[NDArray[np.int32]] = None,
    ) -> NDArray[np.uint8]:
        """Apply BZ reaction rule."""
        N = self.num_states
        new_grid = grid.copy()

        # Compute weighted activation from neighbours
        # Excited states (1..excited_max) contribute positively
        # Refractory states (excited_max+1..N-2) contribute negatively
        excited_mask = (grid >= 1) & (grid <= self._excited_max)
        refractory_mask = (grid > self._excited_max) & (grid < N - 1)

        excited_grid = excited_mask.astype(np.float32)
        refractory_grid = refractory_mask.astype(np.float32)

        if _HAS_SCIPY:
            excited_count = _convolve2d(
                excited_grid, _MOORE_KERNEL_FLOAT, mode="same", boundary="wrap",
            )
            refractory_count = _convolve2d(
                refractory_grid, _MOORE_KERNEL_FLOAT, mode="same", boundary="wrap",
            )
        else:
            excited_count = np.zeros_like(grid, dtype=np.float32)
            refractory_count = np.zeros_like(grid, dtype=np.float32)
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    shifted_e = np.roll(np.roll(excited_grid, -dr, axis=0), -dc, axis=1)
                    shifted_r = np.roll(np.roll(refractory_grid, -dr, axis=0), -dc, axis=1)
                    excited_count += shifted_e
                    refractory_count += shifted_r

        activation = (
            self.weight_excited * excited_count
            + self.weight_refractory * refractory_count
        )

        # Resting cells: excite if activation >= threshold
        excite = (grid == 0) & (activation >= self.threshold)
        new_grid[excite] = 1

        # Advanced states: increment by 1
        advancing = (grid >= 1) & (grid < N - 1)
        new_grid[advancing] = np.minimum(N - 1, grid[advancing].astype(np.int32) + 1).astype(np.uint8)

        # Recovered -> resting
        new_grid[grid == N - 1] = 0

        return new_grid

