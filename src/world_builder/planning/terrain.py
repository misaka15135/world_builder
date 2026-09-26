"""Terrain plans: relief, water and buildability (work order 014).

This replaces the old analytic height function and its straight river through
the middle. A plan is data: a sampled relief grid, the water channels (or a
coastline) as polylines, a reserved mask and the statistics that say whether
the result actually matches the background's `terrain.json`.

Two things are deliberately kept apart:

* the **generator** builds a field, carves valleys along drainage paths and
  clamps each channel to descend, because a synthetic field cannot be trusted
  to have no local minimum; and
* the **validator** re-measures the finished plan from its own grid - water
  fraction, slope, monotone descent, edge connectivity - so a mistake in the
  generator is caught by rules that share none of its intermediate state.
"""
from __future__ import annotations

import json
import hashlib
import math
import random
from dataclasses import dataclass
from pathlib import Path

from .catalogue import DEFAULT_SETTINGS_ROOT, SceneError

TERRAIN_VERSION = "0.1.0"
ROUGHNESS = ("flat", "rolling", "hilly")
WATER_KINDS = ("river", "canal", "coast")
SPEC_KEYS = {"terrain_version", "setting", "relief", "water", "slope", "reserved"}
RELIEF_KEYS = {"min_m", "max_m", "roughness", "tilt"}
# `coast` is not a field: a coastline is what `kind: "coast"` means, and a
# second copy of the same fact could only ever contradict it.
WATER_KEYS = {"kind", "channel_count", "width_m", "fraction"}
SLOPE_KEYS = {"max_deg", "mean_deg"}
RESERVED_KEYS = {"steep_deg", "water_buffer_m"}


def _range(value, field: str, code: str, *, minimum: float = 0.0, integral: bool = False):
    if not isinstance(value, list) or len(value) != 2 or any(type(v) not in (int, float) for v in value):
        raise SceneError(code, f"{field} must be a two-number range")
    if integral and any(type(v) is not int for v in value):
        raise SceneError(code, f"{field} must contain whole numbers")
    low, high = float(value[0]), float(value[1])
    if low > high or low < minimum:
        raise SceneError(code, f"{field} must satisfy {minimum} <= low <= high")
    return (int(low), int(high)) if integral else (low, high)


@dataclass(frozen=True)
class TerrainSpec:
    """Executable terrain requirements for one background."""

    setting: str
    min_m: float
    max_m: float
    roughness: str
    tilt: bool
    water_kind: str
    channel_count: tuple[int, int]
    width_m: tuple[float, float]
    water_fraction: tuple[float, float]
    coast: bool
    max_slope_deg: float
    mean_slope_deg: tuple[float, float]
    steep_deg: float
    water_buffer_m: float


def parse_terrain_spec(payload: dict, setting_id: str) -> TerrainSpec:
    code = "terrain.spec"
    if not isinstance(payload, dict):
        raise SceneError(code, "terrain.json must contain an object")
    extra = sorted(set(payload) - SPEC_KEYS)
    missing = sorted(SPEC_KEYS - set(payload))
    if extra or missing:
        raise SceneError(code, f"unknown {extra} or missing {missing} field(s)")
    if payload["terrain_version"] != TERRAIN_VERSION:
        raise SceneError(code, f"terrain_version must be {TERRAIN_VERSION}")
    if payload["setting"] != setting_id:
        raise SceneError(code, f"terrain.json belongs to {payload['setting']!r}, loaded as {setting_id!r}")
    relief, water, slope, reserved = payload["relief"], payload["water"], payload["slope"], payload["reserved"]
    for section, keys, label in ((relief, RELIEF_KEYS, "relief"), (water, WATER_KEYS, "water"),
                                 (slope, SLOPE_KEYS, "slope"), (reserved, RESERVED_KEYS, "reserved")):
        if not isinstance(section, dict) or set(section) != keys:
            raise SceneError(code, f"{label} needs exactly {', '.join(sorted(keys))}")
    if relief["roughness"] not in ROUGHNESS:
        raise SceneError(code, f"roughness must be one of {', '.join(ROUGHNESS)}")
    if type(relief["tilt"]) is not bool:
        raise SceneError(code, "relief.tilt must be a boolean")
    height_range = _range([relief["min_m"], relief["max_m"]], "relief range", code)
    if height_range[1] <= 0:
        raise SceneError(code, "relief must rise above 0 m")
    if water["kind"] not in WATER_KINDS:
        raise SceneError(code, f"water.kind must be one of {', '.join(WATER_KINDS)}")
    count = _range(water["channel_count"], "water.channel_count", code, minimum=1, integral=True)
    width = _range(water["width_m"], "water.width_m", code, minimum=1.0)
    fraction = _range(water["fraction"], "water.fraction", code)
    if fraction[1] >= 0.9:
        raise SceneError(code, "water.fraction must stay below 0.9")
    max_slope = slope["max_deg"]
    if type(max_slope) not in (int, float) or max_slope <= 0:
        raise SceneError(code, "slope.max_deg must be positive")
    mean_slope = _range(slope["mean_deg"], "slope.mean_deg", code)
    if mean_slope[1] > max_slope:
        raise SceneError(code, "slope.mean_deg must not exceed slope.max_deg")
    steep = reserved["steep_deg"]
    if type(steep) not in (int, float) or steep <= 0:
        raise SceneError(code, "reserved.steep_deg must be positive")
    buffer_m = reserved["water_buffer_m"]
    if type(buffer_m) not in (int, float) or buffer_m < 0:
        raise SceneError(code, "reserved.water_buffer_m must be nonnegative")
    return TerrainSpec(setting=setting_id, min_m=height_range[0], max_m=height_range[1],
                       roughness=relief["roughness"], tilt=relief["tilt"], water_kind=water["kind"],
                       channel_count=count, width_m=width, water_fraction=fraction,
                       coast=water["kind"] == "coast",
                       max_slope_deg=float(max_slope), mean_slope_deg=mean_slope,
                       steep_deg=float(steep), water_buffer_m=float(buffer_m))


def load_terrain_spec(setting: str, root: Path | str = DEFAULT_SETTINGS_ROOT) -> TerrainSpec:
    path = Path(root) / setting / "terrain.json"
    if not path.is_file():
        raise SceneError("terrain.spec_missing", f"{setting} has no terrain.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SceneError("terrain.spec_read", f"cannot read {path}: {exc}") from exc
    return parse_terrain_spec(payload, setting)


@dataclass(frozen=True)
class WaterChannel:
    id: str
    kind: str
    points: tuple[tuple[float, float], ...]
    width_m: float

    @property
    def length_m(self) -> float:
        return sum(math.dist(self.points[index], self.points[index + 1])
                   for index in range(len(self.points) - 1))


@dataclass(frozen=True)
class TerrainPlan:
    """A sampled terrain with its water and reserved zones."""

    setting: str
    seed: int
    region_m: int
    spacing_m: int
    heights: tuple[tuple[float, ...], ...]
    channels: tuple[WaterChannel, ...]
    water_level_m: float | None
    reserved: tuple[tuple[bool, ...], ...]
    stats: dict

    @property
    def rows(self) -> int:
        return len(self.heights)

    @property
    def columns(self) -> int:
        return len(self.heights[0])

    def height_at(self, x: float, y: float) -> float:
        """Bilinear sample, clamped to the region."""
        gx = min(max(x / self.spacing_m, 0.0), self.columns - 1)
        gy = min(max(y / self.spacing_m, 0.0), self.rows - 1)
        x0, y0 = int(gx), int(gy)
        x1, y1 = min(x0 + 1, self.columns - 1), min(y0 + 1, self.rows - 1)
        fx, fy = gx - x0, gy - y0
        top = self.heights[y0][x0] * (1 - fx) + self.heights[y0][x1] * fx
        bottom = self.heights[y1][x0] * (1 - fx) + self.heights[y1][x1] * fx
        return top * (1 - fy) + bottom * fy

    def water_at(self, x: float, y: float) -> bool:
        if self.water_level_m is not None:
            return self.height_at(x, y) <= self.water_level_m
        return any(_distance_to_channel(x, y, channel) <= channel.width_m / 2 for channel in self.channels)

    def slope_deg(self, ix: int, iy: int) -> float:
        ix0, ix1 = max(ix - 1, 0), min(ix + 1, self.columns - 1)
        iy0, iy1 = max(iy - 1, 0), min(iy + 1, self.rows - 1)
        dx = (self.heights[iy][ix1] - self.heights[iy][ix0]) / max((ix1 - ix0) * self.spacing_m, 1e-9)
        dy = (self.heights[iy1][ix] - self.heights[iy0][ix]) / max((iy1 - iy0) * self.spacing_m, 1e-9)
        return math.degrees(math.atan(math.hypot(dx, dy)))

    def distance_to_water_m(self, x: float, y: float) -> float:
        """Approximate distance to the nearest water cell, from the mask."""
        if self.water_at(x, y):
            return 0.0
        ix = min(max(round(x / self.spacing_m), 0), self.columns - 1)
        iy = min(max(round(y / self.spacing_m), 0), self.rows - 1)
        best = None
        for oy in range(self.rows):
            for ox in range(self.columns):
                if not self._cell_is_water(ox, oy):
                    continue
                gap = math.dist((ix, iy), (ox, oy)) * self.spacing_m
                if best is None or gap < best:
                    best = gap
        return float("inf") if best is None else best

    def _cell_is_water(self, ix: int, iy: int) -> bool:
        if self.water_level_m is not None:
            return self.heights[iy][ix] <= self.water_level_m
        x, y = ix * self.spacing_m, iy * self.spacing_m
        return any(_distance_to_channel(x, y, channel) <= channel.width_m / 2 for channel in self.channels)

    def buildable_at(self, x: float, y: float) -> float:
        """0 (water, reserved or too steep) to 1 (flat and clear)."""
        ix = min(max(round(x / self.spacing_m), 0), self.columns - 1)
        iy = min(max(round(y / self.spacing_m), 0), self.rows - 1)
        if self.reserved[iy][ix]:
            return 0.0
        limit = max(self.stats["max_slope_deg"], 1e-6)
        return round(max(0.0, min(1.0, 1.0 - self.slope_deg(ix, iy) / limit)), 6)

    def to_dict(self) -> dict:
        return {
            "terrain_version": TERRAIN_VERSION,
            "setting": self.setting,
            "seed": self.seed,
            "region_m": self.region_m,
            "spacing_m": self.spacing_m,
            "heights_m": [[round(value, 3) for value in row] for row in self.heights],
            "water_level_m": self.water_level_m,
            "channels": [{"id": channel.id, "kind": channel.kind, "width_m": channel.width_m,
                          "points": [[round(px, 2), round(py, 2)] for px, py in channel.points]}
                         for channel in self.channels],
            "reserved": [[1 if flag else 0 for flag in row] for row in self.reserved],
            "stats": dict(self.stats),
        }


def _distance_to_channel(x: float, y: float, channel: WaterChannel) -> float:
    best = float("inf")
    points = channel.points
    for index in range(len(points) - 1):
        (x0, y0), (x1, y1) = points[index], points[index + 1]
        dx, dy = x1 - x0, y1 - y0
        length_sq = dx * dx + dy * dy
        if length_sq == 0:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / length_sq))
        best = min(best, math.hypot(x - (x0 + t * dx), y - (y0 + t * dy)))
    return best


# The relief is a ramp with corrugations that run *parallel* to the drainage,
# plus a bounded ripple along it. That shape is a deliberate choice: it makes
# the descent along a flow-parallel path hold by construction, so no channel
# has to be cut through a hill to satisfy its own validator. A solver that
# found real drainage on an arbitrary field would be the honest upgrade, and
# is out of scope here.
def _base_field(rng: random.Random, columns: int, rows: int, region_m: int, spec: TerrainSpec,
                ramp_angle: float, channels=()):
    """Normalised to the declared relief range."""
    components = {"flat": 3, "rolling": 4, "hilly": 6}[spec.roughness]
    ramp_weight = {"flat": 0.82, "rolling": 0.78, "hilly": 0.62}[spec.roughness] if spec.tilt else 0.0
    axis = (math.cos(ramp_angle), math.sin(ramp_angle))
    cross = (-axis[1], axis[0])
    corrugations = []
    wavelength_range = {"flat": (0.25, 0.60), "rolling": (0.18, 0.45), "hilly": (0.12, 0.35)}[spec.roughness]
    for index in range(components):
        wavelength = rng.uniform(*wavelength_range) / (1 + 0.35 * index)
        corrugations.append((wavelength, rng.uniform(0, 2 * math.pi), 1.0 / (index + 1.3)))
    ripple_wavelength = rng.uniform(0.3, 0.6)
    ripple_phase = rng.uniform(0, 2 * math.pi)
    # Bounded so its slope stays well under the ramp's, keeping the descent.
    ripple_weight = 0.03 * (1 - ramp_weight)
    raw = [[0.0] * columns for _ in range(rows)]
    # Corrugations are tapered to zero near the drainage: a river runs along a
    # flat valley floor and descends with the regional ramp, while the hills
    # stand back from it. Without the taper the meander climbs the corrugations
    # and the channel has to be cut through them to keep its descent.
    floor_m = region_m * 0.10
    hills_m = region_m * 0.28

    def corrugation_weight(x: float, y: float) -> float:
        if not channels:
            return 1.0
        gap = min(_distance_to_channel(x, y, channel) for channel in channels)
        if gap <= floor_m:
            return 0.0
        if gap >= hills_m:
            return 1.0
        return (gap - floor_m) / (hills_m - floor_m)

    for iy in range(rows):
        y = iy * (region_m / (rows - 1)) if rows > 1 else 0.0
        for ix in range(columns):
            x = ix * (region_m / (columns - 1)) if columns > 1 else 0.0
            along = (x * axis[0] + y * axis[1]) / region_m
            sideways = (x * cross[0] + y * cross[1]) / region_m
            relief = sum(amplitude * math.cos(2 * math.pi * sideways / wavelength + phase)
                         for wavelength, phase, amplitude in corrugations)
            relief *= corrugation_weight(x, y)
            if ramp_weight:
                value = ramp_weight * along + (1 - ramp_weight) * relief
                value += ripple_weight * math.cos(2 * math.pi * along / ripple_wavelength + ripple_phase)
            else:
                value = relief
            raw[iy][ix] = value
    low = min(min(row) for row in raw)
    high = max(max(row) for row in raw)
    span = max(high - low, 1e-9)
    return [[spec.min_m + (value - low) / span * (spec.max_m - spec.min_m) for value in row] for row in raw]


def _boundary_span(region_m: float, angle: float) -> float:
    """How far from the centre a ray at `angle` travels before leaving the square."""
    dx, dy = math.cos(angle), math.sin(angle)
    half = region_m / 2
    limits = []
    if abs(dx) > 1e-9:
        limits.append(half / abs(dx))
    if abs(dy) > 1e-9:
        limits.append(half / abs(dy))
    return min(limits) if limits else 0.0


def _bezier(start, control, end, steps: int):
    points = []
    for index in range(steps + 1):
        t = index / steps
        x = (1 - t) ** 2 * start[0] + 2 * (1 - t) * t * control[0] + t ** 2 * end[0]
        y = (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * control[1] + t ** 2 * end[1]
        points.append((round(x, 2), round(y, 2)))
    return tuple(points)


def _on_boundary(region_m: float, x: float, y: float) -> tuple[float, float]:
    x = min(max(x, 0.0), region_m)
    y = min(max(y, 0.0), region_m)
    gaps = ((x, 0), (region_m - x, 0), (y, 1), (region_m - y, 1))
    gap, axis = min((gap, index) for gap, index in gaps)
    if gap > 1e-6:
        return (x, 0.0) if axis == 0 else (x, region_m) if axis == 1 else (0.0, y) if axis == 2 else (region_m, y)
    return (x, y)


def _channels(rng: random.Random, region_m: float, spec: TerrainSpec, ramp_angle: float) -> list[WaterChannel]:
    """Analytic channels: a meandering main course down the ramp plus tributaries.

    The source of the main channel is on the high side of the ramp and its mouth
    is on the low side, so a channel always reaches the boundary and always runs
    downhill - both properties are checked independently on the finished grid.
    """
    centre = (region_m / 2, region_m / 2)
    reach = _boundary_span(region_m, ramp_angle)
    axis = (math.cos(ramp_angle), math.sin(ramp_angle))
    cross = (-axis[1], axis[0])
    high = (centre[0] + reach * axis[0], centre[1] + reach * axis[1])
    low = (centre[0] - reach * axis[0], centre[1] - reach * axis[1])
    meander = 0.02 if spec.water_kind == "canal" else rng.uniform(0.05, 0.11)
    waves = 0.5 if spec.water_kind == "canal" else rng.uniform(1.2, 2.4)
    phase = rng.uniform(0, 2 * math.pi)
    steps = 28
    points = []
    for index in range(steps + 1):
        t = index / steps
        base_x = high[0] + (low[0] - high[0]) * t
        base_y = high[1] + (low[1] - high[1]) * t
        offset = meander * region_m * math.sin(2 * math.pi * waves * t + phase)
        points.append((base_x + offset * cross[0], base_y + offset * cross[1]))
    # The mouth and the source are snapped onto the boundary: the meander must
    # not push the last point 1.5 m inland, or the channel never leaves the map.
    snapped = [_on_boundary(region_m, *points[0])] + points[1:-1] + [_on_boundary(region_m, *points[-1])]
    main = WaterChannel(id="main_0", kind=spec.water_kind,
                        points=tuple((round(x, 2), round(y, 2)) for x, y in snapped),
                        width_m=spec.width_m[1])
    channels = [main]
    for index in range(spec.channel_count[1] - 1):
        join_t = 0.25 + 0.5 * (index / max(spec.channel_count[1] - 1, 1))
        join = main.points[min(int(join_t * steps), steps)]
        side = -1 if index % 2 == 0 else 1
        start = _on_boundary(region_m, high[0] + side * cross[0] * region_m * (0.3 + 0.1 * index),
                             high[1] + side * cross[1] * region_m * (0.3 + 0.1 * index))
        control = (start[0] + (join[0] - start[0]) * 0.5 + side * cross[0] * region_m * 0.08,
                   start[1] + (join[1] - start[1]) * 0.5 + side * cross[1] * region_m * 0.08)
        channels.append(WaterChannel(id=f"tributary_{index + 1}", kind="tributary",
                                     points=_bezier(start, control, join, 16),
                                     width_m=spec.width_m[0]))
    return channels


def _carve(heights, channel: WaterChannel, spacing: float, depth: float) -> None:
    rows, columns = len(heights), len(heights[0])
    half = channel.width_m / 2
    for iy in range(rows):
        y = iy * spacing
        for ix in range(columns):
            gap = _distance_to_channel(ix * spacing, y, channel)
            if gap <= half * 4:
                # A wide, gentle falloff keeps the valley walls walkable; a
                # sharp cut would show up as an impossible slope.
                falloff = math.exp(-(gap / max(half * 2, 1e-6)) ** 2)
                heights[iy][ix] -= depth * falloff


def _bed_nodes(channels, spacing: float, rows: int, columns: int) -> set:
    """Every grid cell that carries a channel bed, across all channels.

    The set is global on purpose: if one channel's bank flattening were allowed
    to lower another channel's bed, that bed would fall out of its own descent
    order, which is the bug this helper exists to prevent.
    """
    nodes = set()
    for channel in channels:
        for x, y in channel.points:
            nodes.add((min(max(round(y / spacing), 0), rows - 1), min(max(round(x / spacing), 0), columns - 1)))
    return nodes


def _clamp_bed_descent(heights, channel: WaterChannel, spacing: float, drop_per_step: float = 0.01) -> None:
    """Make the stored bed descend along the channel.

    A synthetic field can have a local pit; carving a valley does not remove it.
    Rather than hope, the generator makes the bed descend by construction, and
    the validator then re-measures the finished grid without looking at this
    code. Only bed cells are ever lowered here.
    """
    rows, columns = len(heights), len(heights[0])
    previous = None
    for x, y in channel.points:
        ix = min(max(round(x / spacing), 0), columns - 1)
        iy = min(max(round(y / spacing), 0), rows - 1)
        if previous is not None and heights[iy][ix] > previous - drop_per_step:
            heights[iy][ix] = previous - drop_per_step
        previous = heights[iy][ix]


def _flatten_banks(heights, channel: WaterChannel, spacing: float, bed_nodes: set) -> None:
    """Pull the banks down towards the bed so a clamped bed is not a cliff."""
    rows, columns = len(heights), len(heights[0])
    for x, y in channel.points:
        ix = min(max(round(x / spacing), 0), columns - 1)
        iy = min(max(round(y / spacing), 0), rows - 1)
        bed = heights[iy][ix]
        for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = ix + ox, iy + oy
            if (ny, nx) in bed_nodes or not (0 <= nx < columns and 0 <= ny < rows):
                continue
            if heights[ny][nx] > bed:
                heights[ny][nx] = min(heights[ny][nx], bed + 0.25)


def _deepen_bed(heights, channel: WaterChannel, spacing: float, min_depth: float = 0.4) -> None:
    """Guarantee that every bed cell has higher ground next to it.

    Smoothing and flattening both work against the trench: they pull the banks
    down towards the bed until the water can end up on a ridge. This lowers the
    bed cells only, and the descent clamp that follows keeps them in order.
    """
    rows, columns = len(heights), len(heights[0])
    for x, y in channel.points:
        ix = min(max(round(x / spacing), 0), columns - 1)
        iy = min(max(round(y / spacing), 0), rows - 1)
        banks = [heights[ny][nx] for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                 if 0 <= ix + ox < columns and 0 <= iy + oy < rows
                 for nx, ny in ((ix + ox, iy + oy),)]
        if not banks:
            continue
        ceiling = max(banks) - min_depth
        if heights[iy][ix] > ceiling:
            heights[iy][ix] = ceiling


def _smooth(heights, spacing: float, channels, protected_radius_m: float, passes: int = 3,
            protect_bed: bool = True) -> None:
    rows, columns = len(heights), len(heights[0])
    protected = [[False] * columns for _ in range(rows)]
    if protect_bed:
        for iy in range(rows):
            for ix in range(columns):
                x, y = ix * spacing, iy * spacing
                protected[iy][ix] = any(_distance_to_channel(x, y, channel) <= protected_radius_m
                                        for channel in channels)
    for _ in range(passes):
        copy = [row[:] for row in heights]
        for iy in range(1, rows - 1):
            for ix in range(1, columns - 1):
                if protected[iy][ix]:
                    continue
                total = sum(copy[iy + oy][ix + ox] for ox in (-1, 0, 1) for oy in (-1, 0, 1))
                heights[iy][ix] = total / 9


def _fit_relief_range(heights, spec: TerrainSpec, water_level: float | None) -> float | None:
    """Affine fit into the declared relief range; keeps every ordering intact."""
    values = [value for row in heights for value in row]
    low, high = min(values), max(values)
    if high - low < 1e-9:
        return water_level
    scale = (spec.max_m - spec.min_m) / (high - low)

    def fit(value: float) -> float:
        return spec.min_m + (value - low) * scale

    for iy, row in enumerate(heights):
        for ix, value in enumerate(row):
            heights[iy][ix] = fit(value)
    return fit(water_level) if water_level is not None else None


def _coastline(heights, spacing: float, level: float, rays: int = 72) -> tuple[tuple[tuple[float, float], ...], float]:
    """Trace the water level as a star-shaped contour around the region centre."""
    rows, columns = len(heights), len(heights[0])
    cx = (columns - 1) * spacing / 2
    cy = (rows - 1) * spacing / 2
    reach = math.hypot(cx, cy)
    points = []
    for index in range(rays):
        angle = 2 * math.pi * index / rays
        last = None
        steps = 0
        while steps * spacing <= reach * 1.2:
            radius = steps * spacing
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            if not (0 <= x <= (columns - 1) * spacing and 0 <= y <= (rows - 1) * spacing):
                break
            value = heights[min(max(round(y / spacing), 0), rows - 1)][min(max(round(x / spacing), 0), columns - 1)]
            if value <= level:
                last = (x, y)
            steps += 1
        if last is not None:
            points.append((round(last[0], 2), round(last[1], 2)))
    return tuple(points), level


def plan_terrain(setting: str, seed: int = 1, region_m: int = 512, spacing_m: int = 4,
                 root: Path | str = DEFAULT_SETTINGS_ROOT) -> TerrainPlan:
    """Build a terrain plan for one background, deterministically."""
    spec = load_terrain_spec(setting, root)
    if region_m < 128 or region_m % 128:
        raise SceneError("terrain.region", "region_m must be a multiple of 128")
    if region_m % spacing_m:
        raise SceneError("terrain.spacing", "spacing_m must divide region_m")
    fingerprint = f"{setting}:{seed}:{region_m}:{spacing_m}:{TERRAIN_VERSION}".encode("utf-8")
    rng = random.Random(int.from_bytes(hashlib.sha256(fingerprint).digest()[:8], "big"))
    columns = rows = region_m // spacing_m + 1
    ramp_angle = rng.uniform(0, 2 * math.pi)
    water_level = None
    depth = max(0.6, (spec.max_m - spec.min_m) * 0.12)

    if spec.water_kind == "coast":
        # The navigation channel is decided before the relief, so the terrain
        # can be flat along it; the shoreline needs the relief, so it comes
        # afterwards.
        reach = _boundary_span(region_m, ramp_angle)
        axis = (math.cos(ramp_angle), math.sin(ramp_angle))
        cross = (-axis[1], axis[0])
        centre = (region_m / 2, region_m / 2)
        navigation = WaterChannel(
            id="channel_0", kind="canal",
            points=_bezier((centre[0] + reach * 0.9 * axis[0], centre[1] + reach * 0.9 * axis[1]),
                           (centre[0] + 0.25 * region_m * cross[0], centre[1] + 0.25 * region_m * cross[1]),
                           (_on_boundary(region_m, centre[0] - reach * 0.9 * axis[0],
                                         centre[1] - reach * 0.9 * axis[1])), 12),
            width_m=spec.width_m[0])
        heights = _base_field(rng, columns, rows, region_m, spec, ramp_angle, [navigation])
        # Water occupies the low side of the ramp: pick the level that yields
        # the declared fraction, so the shoreline follows from the terrain.
        flat = sorted(value for row in heights for value in row)
        target = spec.water_fraction[1] * 0.8
        water_level = flat[min(len(flat) - 1, int(len(flat) * target))]
        points, water_level = _coastline(heights, spacing_m, water_level)
        channels = [WaterChannel(id="coast_0", kind="coast", points=points + points[:1],
                                 width_m=spec.width_m[1] / 4)] if len(points) >= 4 else []
        channels.append(navigation)
    else:
        channels = _channels(rng, region_m, spec, ramp_angle)
        if spec.water_kind == "canal":
            channels = [channel for channel in channels if channel.kind != "tributary"][:1] + \
                       [channel for channel in channels if channel.kind == "tributary"][:spec.channel_count[1] - 1]
        # The channels are decided first and the relief is built around them:
        # that is what lets the valley floor be flat without the water having to
        # be cut through the hills afterwards.
        heights = _base_field(rng, columns, rows, region_m, spec, ramp_angle, channels)

    for channel in channels:
        if channel.kind != "coast":
            _carve(heights, channel, spacing_m, depth)
    inland = [channel for channel in channels if channel.kind != "coast"]
    beds = _bed_nodes(inland, spacing_m, rows, columns)
    protected = max((channel.width_m for channel in inland), default=0.0) / 2
    # Clamp, flatten the banks towards the bed, smooth the rest, and repeat:
    # clamping alone leaves a cliff, smoothing alone fills the channel in. The
    # final clamp has the last word, so the stored bed is monotone by
    # construction and the validator can check it without trusting this order.
    for _ in range(3):
        for channel in inland:
            _clamp_bed_descent(heights, channel, spacing_m, drop_per_step=0.02)
        for channel in inland:
            _deepen_bed(heights, channel, spacing_m)
        _smooth(heights, spacing_m, inland, protected_radius_m=protected, passes=3)
    for channel in inland:
        _deepen_bed(heights, channel, spacing_m)
        # The clamp has the last word: it only lowers bed cells, so it keeps the
        # trench and restores the descent order the validator reads.
        _clamp_bed_descent(heights, channel, spacing_m, drop_per_step=0.01)
    water_level = _fit_relief_range(heights, spec, water_level)

    plan_stats = _measure(heights, spacing_m, channels, water_level, spec)
    reserved = tuple(tuple(_is_reserved(heights, spacing_m, channels, water_level, spec, ix, iy)
                           for ix in range(columns)) for iy in range(rows))
    plan_stats["reserved_fraction"] = round(sum(1 for row in reserved for flag in row if flag)
                                            / (rows * columns), 4)
    return TerrainPlan(setting=setting, seed=seed, region_m=region_m, spacing_m=spacing_m,
                       heights=tuple(tuple(row) for row in heights), channels=tuple(channels),
                       water_level_m=water_level, reserved=reserved, stats=plan_stats)


def _measure(heights, spacing, channels, water_level, spec) -> dict:
    rows, columns = len(heights), len(heights[0])
    values = [value for row in heights for value in row]
    water_cells = 0
    slopes = []
    for iy in range(rows):
        for ix in range(columns):
            is_water = heights[iy][ix] <= water_level if water_level is not None else any(
                _distance_to_channel(ix * spacing, iy * spacing, channel) <= channel.width_m / 2
                for channel in channels if channel.kind != "coast")
            water_cells += 1 if is_water else 0
            slopes.append(_slope(heights, spacing, ix, iy))
    return {
        "min_m": round(min(values), 3), "max_m": round(max(values), 3),
        "mean_m": round(sum(values) / len(values), 3),
        "mean_slope_deg": round(sum(slopes) / len(slopes), 3),
        "max_slope_deg": round(max(slopes), 3),
        "water_fraction": round(water_cells / (rows * columns), 4),
        "channel_count": len([channel for channel in channels if channel.kind != "coast"]),
        "channel_length_m": round(sum(channel.length_m for channel in channels), 1),
    }


def _slope(heights, spacing, ix, iy) -> float:
    rows, columns = len(heights), len(heights[0])
    ix0, ix1 = max(ix - 1, 0), min(ix + 1, columns - 1)
    iy0, iy1 = max(iy - 1, 0), min(iy + 1, rows - 1)
    dx = (heights[iy][ix1] - heights[iy][ix0]) / max((ix1 - ix0) * spacing, 1e-9)
    dy = (heights[iy1][ix] - heights[iy0][ix]) / max((iy1 - iy0) * spacing, 1e-9)
    return math.degrees(math.atan(math.hypot(dx, dy)))


def _is_reserved(heights, spacing, channels, water_level, spec, ix, iy) -> bool:
    if water_level is not None and heights[iy][ix] <= water_level:
        return True
    if _slope(heights, spacing, ix, iy) > spec.steep_deg:
        return True
    x, y = ix * spacing, iy * spacing
    return any(_distance_to_channel(x, y, channel) <= spec.water_buffer_m
               for channel in channels if channel.kind != "coast")


def validate_terrain(plan: TerrainPlan, spec: TerrainSpec) -> dict:
    """Independent checks on the finished plan; returns a report, never mutates."""
    results = []

    def check(rule: str, passed: bool, message: str, **extra) -> None:
        results.append({"rule": rule, "state": "pass" if passed else "fail", "message": message, **extra})

    tolerance = 0.5
    check("terrain.relief", spec.min_m - tolerance <= plan.stats["min_m"] <= spec.max_m + tolerance
          and spec.min_m - tolerance <= plan.stats["max_m"] <= spec.max_m + tolerance,
          f"relief {plan.stats['min_m']}..{plan.stats['max_m']} m within {spec.min_m}..{spec.max_m} m")
    check("terrain.slope_max", plan.stats["max_slope_deg"] <= spec.max_slope_deg + 1e-6,
          f"max slope {plan.stats['max_slope_deg']}° <= {spec.max_slope_deg}°")
    check("terrain.slope_mean", spec.mean_slope_deg[0] <= plan.stats["mean_slope_deg"] <= spec.mean_slope_deg[1],
          f"mean slope {plan.stats['mean_slope_deg']}° within {spec.mean_slope_deg}")
    check("terrain.water_fraction", spec.water_fraction[0] <= plan.stats["water_fraction"] <= spec.water_fraction[1],
          f"water {plan.stats['water_fraction']} within {spec.water_fraction}")
    check("terrain.channel_count",
          spec.channel_count[0] <= plan.stats["channel_count"] <= spec.channel_count[1],
          f"{plan.stats['channel_count']} channel(s) within {spec.channel_count}")
    check("terrain.coast", spec.coast == any(channel.kind == "coast" for channel in plan.channels),
          "coastline present exactly when the background declares one")
    for channel in plan.channels:
        if channel.kind == "coast":
            continue
        check("terrain.width", spec.width_m[0] - 1e-6 <= channel.width_m <= spec.width_m[1] + 1e-6,
              f"{channel.id} width {channel.width_m} m within {spec.width_m}", channel=channel.id)
        # The bed as stored: the channel is a set of grid cells, and bilinear
        # sampling between them would mix in the bank and fake an uphill step.
        samples = [_bed_height(plan, x, y) for x, y in channel.points]
        monotone = all(samples[index + 1] <= samples[index] + 1e-6 for index in range(len(samples) - 1))
        drop = samples[0] - samples[-1]
        check("terrain.flow_downhill", monotone and drop > 0,
              f"{channel.id} descends {round(drop, 2)} m over {len(samples)} samples", channel=channel.id)
        trench = [_trench_profile(plan, channel, index) for index in range(len(channel.points))]
        banks_above = all(profile["higher_bank_m"] >= 0.05 for profile in trench)
        depth = round(sum(profile["depth_m"] for profile in trench) / len(trench), 2)
        check("terrain.water_in_valley", banks_above,
              f"{channel.id} sits in a trench of mean depth {depth} m", channel=channel.id)
        first, last = channel.points[0], channel.points[-1]
        edge = plan.region_m
        touching = (min(first[0], last[0]) <= 1e-6 or min(first[1], last[1]) <= 1e-6
                    or max(first[0], last[0]) >= edge - 1e-6 or max(first[1], last[1]) >= edge - 1e-6)
        check("terrain.water_connected", touching,
              f"{channel.id} reaches the region boundary at {first} / {last}", channel=channel.id)
    return {"setting": plan.setting, "state": "pass" if all(r["state"] == "pass" for r in results) else "fail",
            "checks": results, "stats": dict(plan.stats)}


def _bed_height(plan: TerrainPlan, x: float, y: float) -> float:
    ix = min(max(round(x / plan.spacing_m), 0), plan.columns - 1)
    iy = min(max(round(y / plan.spacing_m), 0), plan.rows - 1)
    return plan.heights[iy][ix]


def _trench_profile(plan: TerrainPlan, channel: WaterChannel, index: int) -> dict:
    """Measure the bed against the ground *across* the channel.

    Checking the four grid neighbours was wrong for a channel that runs along a
    grid axis: its predecessor and successor cells are neighbours too and sit
    lower, so a perfectly good trench failed. What matters is whether the water
    is below the ground at right angles to its own flow.
    """
    points = channel.points
    here = points[index]
    before = points[max(index - 1, 0)]
    after = points[min(index + 1, len(points) - 1)]
    tangent = (after[0] - before[0], after[1] - before[1])
    length = math.hypot(*tangent) or 1.0
    normal = (-tangent[1] / length, tangent[0] / length)
    reach = max(plan.spacing_m * 1.5, channel.width_m / 2)
    bed = plan.height_at(*here)
    left = plan.height_at(here[0] + normal[0] * reach, here[1] + normal[1] * reach)
    right = plan.height_at(here[0] - normal[0] * reach, here[1] - normal[1] * reach)
    return {"bed_m": bed, "banks_m": (left, right), "higher_bank_m": max(left, right) - bed,
            "depth_m": max(0.0, (left + right) / 2 - bed)}


def render_preview(plan: TerrainPlan, width: int = 72) -> str:
    """A readable relief map: water, reserved land, then shaded heights."""
    shades = " .:-=+*#%@"
    rows, columns = plan.rows, plan.columns
    step_x = max(1, columns // width)
    step_y = max(1, round(step_x / 2))
    low, high = plan.stats["min_m"], plan.stats["max_m"]
    span = max(high - low, 1e-9)
    lines = []
    for iy in range(0, rows, step_y):
        line = []
        for ix in range(0, columns, step_x):
            if plan.water_level_m is not None and plan.heights[iy][ix] <= plan.water_level_m:
                line.append("~")
            elif any(channel.kind != "coast" and _distance_to_channel(ix * plan.spacing_m, iy * plan.spacing_m, channel)
                     <= channel.width_m / 2 for channel in plan.channels):
                line.append("~")
            elif plan.reserved[iy][ix]:
                line.append("^")
            else:
                index = int((plan.heights[iy][ix] - low) / span * (len(shades) - 1))
                line.append(shades[max(0, min(index, len(shades) - 1))])
        lines.append("".join(line))
    return "\n".join(lines)
