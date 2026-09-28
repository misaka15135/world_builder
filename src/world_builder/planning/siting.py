"""District ownership and siting: blocks, skeleton and building envelopes (work order 016).

This is stage D. It turns a terrain plan and a landmark catalogue into:

* `domains` - holdings that own several blocks (a castle, a port authority, the
  outer wards), each with its own height and footprint factors;
* `blocks` - variable-size rectangles with a use, because a city is not a
  uniform grid;
* a skeleton of arterials, local streets, quays and rail;
* `sites` - one envelope per building the brief demands, with the maximum
  footprint and height that stage E must design inside.

The rules that say how much of what goes where live in `settings/<id>/districts.json`,
so a new background is still data rather than code.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

from .brief import SceneBrief
from .catalogue import DEFAULT_SETTINGS_ROOT, SceneError, SettingPack
from .terrain import TerrainPlan, _distance_to_channel

DISTRICTS_VERSION = "0.1.0"
ROLE_USES = {
    "housing": ("residential", "market"),
    "commerce": ("market", "civic"),
    "craft": ("craft", "industrial", "market"),
    "civic": ("civic", "market"),
    "landmark": ("civic", "green", "harbour"),
    "infrastructure": ("industrial", "harbour", "market"),
    "defence": ("green", "residential"),
    "green": ("green", "civic"),
    "vessel": ("harbour",),
}


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
class DistrictSpec:
    setting: str
    block_area_m2: tuple[float, float]
    target_blocks: tuple[int, int]
    uses: dict
    domains: dict
    arterial_width_m: tuple[float, float]
    local_width_m: tuple[float, float]


def parse_districts_spec(payload: dict, setting: str) -> DistrictSpec:
    code = "districts.spec"
    required = {"districts_version", "setting", "block_area_m2", "target_blocks", "uses", "domains", "roads"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise SceneError(code, f"districts.json must contain exactly {', '.join(sorted(required))}")
    if payload["districts_version"] != DISTRICTS_VERSION:
        raise SceneError(code, f"districts_version must be {DISTRICTS_VERSION}")
    if payload["setting"] != setting:
        raise SceneError(code, f"districts.json belongs to {payload['setting']!r}, loaded as {setting!r}")
    uses = payload["uses"]
    if not isinstance(uses, dict) or not uses:
        raise SceneError(code, "uses must be a nonempty mapping")
    share_total = 0.0
    for use, rules in uses.items():
        if not isinstance(rules, dict):
            raise SceneError(code, f"{use} rules must be an object")
        keys = {"share", "centre_distance", "road_width_m", "height_factor", "footprint_factor"}
        if set(rules) - keys - {"wants_water"}:
            raise SceneError(code, f"{use} has unknown field(s): {sorted(set(rules) - keys - {'wants_water'})}")
        if keys - set(rules):
            raise SceneError(code, f"{use} is missing {sorted(keys - set(rules))}")
        share = _range(rules["share"], f"{use}.share", code)
        _range(rules["centre_distance"], f"{use}.centre_distance", code)
        if not 0 < rules["road_width_m"] <= 40:
            raise SceneError(code, f"{use}.road_width_m must be between 0 and 40 m")
        if not 0.1 <= rules["height_factor"] <= 3 or not 0.1 <= rules["footprint_factor"] <= 3:
            raise SceneError(code, f"{use} factors must stay within 0.1 and 3")
        share_total += share[0]
    if share_total > 1.0 + 1e-9:
        raise SceneError(code, f"the minimum shares of all uses sum to {round(share_total, 3)} > 1")
    domains = payload["domains"]
    if not isinstance(domains, dict) or not domains:
        raise SceneError(code, "domains must be a nonempty mapping")
    for name, rules in domains.items():
        keys = {"kind", "height_factor", "footprint_factor", "prefers"}
        if not isinstance(rules, dict) or set(rules) != keys:
            raise SceneError(code, f"{name} must contain exactly {', '.join(sorted(keys))}")
        unknown = [use for use in rules["prefers"] if use not in uses]
        if unknown:
            raise SceneError(code, f"{name} prefers unknown use(s): {unknown}")
        if not 0.1 <= rules["height_factor"] <= 3 or not 0.1 <= rules["footprint_factor"] <= 3:
            raise SceneError(code, f"{name} factors must stay within 0.1 and 3")
    roads = payload["roads"]
    if not isinstance(roads, dict) or set(roads) != {"arterial_width_m", "local_width_m"}:
        raise SceneError(code, "roads must hold arterial_width_m and local_width_m")
    return DistrictSpec(setting=setting,
                        block_area_m2=_range(payload["block_area_m2"], "block_area_m2", code, minimum=100),
                        target_blocks=_range(payload["target_blocks"], "target_blocks", code, minimum=4, integral=True),
                        uses={use: {**rules, "wants_water": bool(rules.get("wants_water", False))}
                              for use, rules in uses.items()},
                        domains=domains,
                        arterial_width_m=_range(roads["arterial_width_m"], "arterial_width_m", code, minimum=2),
                        local_width_m=_range(roads["local_width_m"], "local_width_m", code, minimum=1.5))


def load_districts_spec(setting: str, root: Path | str = DEFAULT_SETTINGS_ROOT) -> DistrictSpec:
    path = Path(root) / setting / "districts.json"
    if not path.is_file():
        raise SceneError("districts.spec_missing", f"{setting} has no districts.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SceneError("districts.spec_read", f"cannot read {path}: {exc}") from exc
    return parse_districts_spec(payload, setting)


@dataclass(frozen=True)
class Block:
    id: str
    x0: float
    y0: float
    x1: float
    y1: float
    use: str
    domain: str

    @property
    def centre(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    @property
    def area_m2(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)


@dataclass(frozen=True)
class Domain:
    id: str
    kind: str
    height_factor: float
    footprint_factor: float
    prefers: tuple[str, ...]
    block_ids: tuple[str, ...]
    centre: tuple[float, float]


@dataclass(frozen=True)
class Road:
    id: str
    kind: str
    points: tuple[tuple[float, float], ...]
    width_m: float

    @property
    def length_m(self) -> float:
        return sum(math.dist(self.points[index], self.points[index + 1])
                   for index in range(len(self.points) - 1))


@dataclass(frozen=True)
class Bridge:
    id: str
    road_id: str
    channel_id: str
    start: tuple[float, float]
    end: tuple[float, float]
    width_m: float


@dataclass(frozen=True)
class Site:
    id: str
    type: str
    role: str
    design_state: str
    block_id: str
    domain_id: str
    x0: float
    y0: float
    x1: float
    y1: float
    max_height_m: float
    max_storeys: int
    needs: tuple[str, ...]
    adjacency: tuple[str, ...]

    @property
    def centre(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    @property
    def area_m2(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)


@dataclass(frozen=True)
class Work:
    """A linear work - a wall, a pier, a rail line - as a corridor.

    Linear works do not fit a block envelope: a city wall crosses many blocks
    and a pier runs into the water. They are sited as corridors instead, and
    stage E designs along them rather than inside a rectangle.
    """

    id: str
    type: str
    role: str
    design_state: str
    kind: str
    points: tuple[tuple[float, float], ...]
    width_m: float
    length_m: float


@dataclass(frozen=True)
class SitingPlan:
    setting: str
    seed: int
    region_m: int
    blocks: tuple[Block, ...]
    domains: tuple[Domain, ...]
    roads: tuple[Road, ...]
    bridges: tuple[Bridge, ...]
    sites: tuple[Site, ...]
    works: tuple[Work, ...]
    stats: dict

    def block(self, block_id: str) -> Block:
        return next(block for block in self.blocks if block.id == block_id)

    def sites_of(self, type_name: str) -> tuple[Site, ...]:
        return tuple(site for site in self.sites if site.type == type_name)

    def to_dict(self) -> dict:
        return {
            "districts_version": DISTRICTS_VERSION,
            "setting": self.setting,
            "seed": self.seed,
            "region_m": self.region_m,
            "domains": [{"id": domain.id, "kind": domain.kind, "height_factor": domain.height_factor,
                         "footprint_factor": domain.footprint_factor, "prefers": list(domain.prefers),
                         "block_ids": list(domain.block_ids), "centre": list(domain.centre)}
                        for domain in self.domains],
            "blocks": [{"id": block.id, "rect": [block.x0, block.y0, block.x1, block.y1],
                        "use": block.use, "domain": block.domain, "area_m2": round(block.area_m2, 1)}
                       for block in self.blocks],
            "roads": [{"id": road.id, "kind": road.kind, "width_m": road.width_m,
                       "points": [[round(x, 2), round(y, 2)] for x, y in road.points]} for road in self.roads],
            "bridges": [{"id": bridge.id, "road_id": bridge.road_id, "channel_id": bridge.channel_id,
                         "start": list(bridge.start), "end": list(bridge.end), "width_m": bridge.width_m}
                        for bridge in self.bridges],
            "sites": [{"id": site.id, "type": site.type, "role": site.role, "design_state": site.design_state,
                       "block_id": site.block_id, "domain_id": site.domain_id,
                       "rect": [site.x0, site.y0, site.x1, site.y1],
                       "max_height_m": site.max_height_m, "max_storeys": site.max_storeys,
                       "needs": list(site.needs), "adjacency": list(site.adjacency)} for site in self.sites],
            "works": [{"id": work.id, "type": work.type, "role": work.role, "design_state": work.design_state,
                       "kind": work.kind, "width_m": work.width_m, "length_m": round(work.length_m, 1),
                       "points": [[round(x, 2), round(y, 2)] for x, y in work.points]}
                      for work in self.works],
            "stats": dict(self.stats),
        }


def _bsp_blocks(region_m: int, spec: DistrictSpec, rng: random.Random) -> list[tuple[float, float, float, float]]:
    """Recursive subdivision into variable-size rectangles."""
    target_min, target_max = spec.target_blocks
    largest, smallest = spec.block_area_m2[1], spec.block_area_m2[0]
    blocks = [(0.0, 0.0, float(region_m), float(region_m))]
    while True:
        splittable = [rect for rect in blocks
                      if (rect[2] - rect[0]) * (rect[3] - rect[1]) > largest
                      and min(rect[2] - rect[0], rect[3] - rect[1]) >= math.sqrt(smallest)]
        if not splittable and len(blocks) < target_min:
            splittable = [rect for rect in blocks
                          if min(rect[2] - rect[0], rect[3] - rect[1]) >= math.sqrt(smallest)]
        if not splittable or len(blocks) >= target_max:
            break
        rect = max(splittable, key=lambda item: (item[2] - item[0]) * (item[3] - item[1]))
        blocks.remove(rect)
        x0, y0, x1, y1 = rect
        width, height = x1 - x0, y1 - y0
        fraction = rng.uniform(0.40, 0.60)
        if width > height:
            cut = x0 + width * fraction
            blocks.extend([(x0, y0, cut, y1), (cut, y0, x1, y1)])
        else:
            cut = y0 + height * fraction
            blocks.extend([(x0, y0, x1, cut), (x0, cut, x1, y1)])
    return sorted(blocks, key=lambda rect: (rect[1], rect[0]))


def _assign_uses(rects, region_m: int, spec: DistrictSpec, terrain: TerrainPlan) -> list[str]:
    """Greedy quota assignment: every use gets its declared share of the blocks."""
    uses = list(spec.uses)
    total = len(rects)
    quotas = {}
    for index, use in enumerate(uses):
        low, high = spec.uses[use]["share"]
        share = (low + high) / 2
        quotas[use] = max(1, int(round(share * total)))
    while sum(quotas.values()) > total:
        biggest = max(quotas, key=lambda use: quotas[use])
        quotas[biggest] -= 1
    while sum(quotas.values()) < total:
        quotas[uses[sum(quotas.values()) % len(uses)]] += 1

    scored = []
    for index, (x0, y0, x1, y1) in enumerate(rects):
        centre = ((x0 + x1) / 2, (y0 + y1) / 2)
        distance = math.dist(centre, (region_m / 2, region_m / 2)) / (region_m * 0.7071)
        water = terrain.distance_to_water_m(*centre)
        slope = terrain.slope_deg(min(max(round(centre[0] / terrain.spacing_m), 0), terrain.columns - 1),
                                  min(max(round(centre[1] / terrain.spacing_m), 0), terrain.rows - 1))
        for use, rules in spec.uses.items():
            low, high = rules["centre_distance"]
            centre_fit = 1.0 - min(1.0, abs(distance - (low + high) / 2) / max((high - low) / 2, 0.2))
            water_fit = 1.0 - min(1.0, water / 120.0) if rules["wants_water"] else 1.0
            flat_fit = 1.0 - min(1.0, slope / 12.0)
            score = 2.0 * centre_fit + 1.5 * water_fit + 0.5 * flat_fit
            if rules["wants_water"] and water > 150:
                # A harbour district 240 m inland is not a harbour district; the
                # quota must be filled by blocks that can actually reach water.
                score = -1e9
            scored.append((score, index, use))
    scored.sort(key=lambda item: -item[0])
    assigned = [None] * total
    for score, index, use in scored:
        if assigned[index] is None and quotas.get(use, 0) > 0:
            assigned[index] = use
            quotas[use] -= 1
    for index, use in enumerate(assigned):
        if use is None:
            assigned[index] = max(quotas, key=lambda candidate: quotas[candidate])
            quotas[assigned[index]] -= 1
    return assigned


def _assign_domains(blocks, spec: DistrictSpec, region_m: int) -> dict[str, str]:
    """Anchor each domain on its best block, then give every block its owner."""
    anchors: dict[str, tuple[float, float]] = {}
    remaining = list(blocks)
    for name, rules in spec.domains.items():
        def affinity(block):
            distance = math.dist(block.centre, (region_m / 2, region_m / 2)) / (region_m * 0.7071)
            preference = 1.0 if block.use in rules["prefers"] else 0.0
            centre_fit = 1.0 - distance
            return preference * 2.0 + centre_fit
        best = max(remaining, key=affinity)
        anchors[name] = best.centre
        remaining = [block for block in remaining if block is not best]
        if not remaining:
            break
    ownership = {}
    for block in blocks:
        def score(name):
            rules = spec.domains[name]
            preference = 1.0 if block.use in rules["prefers"] else 0.0
            distance = math.dist(block.centre, anchors[name])
            return preference * 2.0 + 1.0 / (1.0 + distance / (region_m * 0.2))
        ownership[block.id] = max(spec.domains, key=score)
    # Every declared domain owns something, otherwise its factors are decorative.
    for name in spec.domains:
        if name not in ownership.values():
            candidate = max(blocks, key=lambda block: 1.0 if block.use in spec.domains[name]["prefers"] else 0.0)
            ownership[candidate.id] = name
    return ownership


def _spine(anchors, region_m: float, rng: random.Random):
    """An arterial that visits every domain anchor and then leaves the map."""
    order = list(anchors)
    ordered = [order.pop(0)]
    while order:
        last = ordered[-1]
        nearest = min(order, key=lambda name: math.dist(anchors[name], anchors[last]))
        ordered.append(nearest)
        order.remove(nearest)
    points = [anchors[ordered[0]]]
    for name in ordered[1:]:
        target = anchors[name]
        start = points[-1]
        # Enough bend that the arterial network is polygonal rather than a set
        # of near-axis chords: a city that only knows 0° and 90° looks printed.
        control = ((start[0] + target[0]) / 2 + rng.uniform(-0.13, 0.13) * region_m,
                   (start[1] + target[1]) / 2 + rng.uniform(-0.13, 0.13) * region_m)
        for step in range(1, 5):
            t = step / 4
            x = (1 - t) ** 2 * start[0] + 2 * (1 - t) * t * control[0] + t ** 2 * target[0]
            y = (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * control[1] + t ** 2 * target[1]
            points.append((min(max(x, 0.0), region_m), min(max(y, 0.0), region_m)))
    # Leave the map so the arterial connects to the outside world.
    last = points[-1]
    edge = min(((last[0], 0.0), (last[0], region_m), (0.0, last[1]), (region_m, last[1])),
               key=lambda point: math.dist(point, last))
    points.append(edge)
    return tuple(points)


def _bridges_for(road: Road, terrain: TerrainPlan, index: int):
    bridges = []
    for channel in terrain.channels:
        if channel.kind == "coast":
            continue
        runs: list[list[tuple[float, float]]] = []
        current: list[tuple[float, float]] = []
        for point_index in range(len(road.points) - 1):
            start, end = road.points[point_index], road.points[point_index + 1]
            # Sample every ~4 m: the old fifth-of-a-segment sampling stepped
            # 40 m at a time across a 20 m river and "found" crossings that
            # were not there, and missed the ones that were.
            slices = max(1, int(math.dist(start, end) // 4))
            for step in range(slices):
                t0, t1 = step / slices, (step + 1) / slices
                a = (start[0] + (end[0] - start[0]) * t0, start[1] + (end[1] - start[1]) * t0)
                b = (start[0] + (end[0] - start[0]) * t1, start[1] + (end[1] - start[1]) * t1)
                if _distance_to_channel(*b, channel) <= channel.width_m / 2:
                    if not current:
                        current.append(a)
                    current.append(b)
                elif current:
                    runs.append(current)
                    current = []
        if current:
            runs.append(current)
        # One bridge per crossing: a road that crosses a river twice needs two
        # spans, and a span that swallowed the dry land between them is not a
        # bridge at all.
        for run_index, run in enumerate(runs):
            if len(run) < 3:
                continue
            bridges.append(Bridge(id=f"bridge_{index}_{run_index}_{channel.id}", road_id=road.id,
                                  channel_id=channel.id, start=run[0], end=run[-1], width_m=road.width_m))
    return bridges


def _site_footprint(entry, domain: Domain, use_rules) -> tuple[float, float]:
    if entry.footprint_m2_range is None:
        raise SceneError("siting.linear_entry",
                         f"{entry.type} is a linear work and has no footprint envelope")
    area = (entry.footprint_m2_range[0] + entry.footprint_m2_range[1]) / 2
    area *= domain.footprint_factor * use_rules["footprint_factor"]
    area = min(max(area, entry.footprint_m2_range[0]), entry.footprint_m2_range[1])
    width = math.sqrt(area * 1.2)
    return (round(width, 2), round(area / width, 2))


def _site_height(entry, domain: Domain, use_rules, storey_h: float = 3.0) -> tuple[float, int]:
    low, high = entry.height_m_range if entry.height_m_range else (3.0, 9.0)
    height = (low + high) / 2 * domain.height_factor * use_rules["height_factor"]
    height = min(max(height, low), high)
    return (round(height, 2), max(1, int(height // storey_h)))


def plan_siting(brief: SceneBrief, pack: SettingPack, terrain: TerrainPlan,
                spec: DistrictSpec | None = None) -> SitingPlan:
    """Build blocks, ownership, skeleton and one envelope per demanded building."""
    spec = spec or load_districts_spec(pack.id, pack.root.parent)
    fingerprint = f"{pack.id}:{brief.seed}:{brief.region_m}:{brief.digest()}".encode("utf-8")
    rng = random.Random(int.from_bytes(hashlib.sha256(fingerprint).digest()[:8], "big"))
    rects = _bsp_blocks(brief.region_m, spec, rng)
    uses = _assign_uses(rects, brief.region_m, spec, terrain)
    blocks = tuple(Block(id=f"block_{index:03d}", x0=rect[0], y0=rect[1], x1=rect[2], y1=rect[3],
                         use=uses[index], domain="") for index, rect in enumerate(rects))
    ownership = _assign_domains(blocks, spec, brief.region_m)
    blocks = tuple(Block(**{**block.__dict__, "domain": ownership[block.id]}) for block in blocks)

    domains = []
    for name, rules in spec.domains.items():
        owned = [block for block in blocks if block.domain == name]
        if not owned:
            continue
        centre = (sum(block.centre[0] for block in owned) / len(owned),
                  sum(block.centre[1] for block in owned) / len(owned))
        domains.append(Domain(id=name, kind=rules["kind"], height_factor=rules["height_factor"],
                              footprint_factor=rules["footprint_factor"], prefers=tuple(rules["prefers"]),
                              block_ids=tuple(block.id for block in owned), centre=centre))
    anchors = {name: (next(block for block in blocks if block.domain == name).centre
                      if name in {block.domain for block in blocks} else (brief.region_m / 2, brief.region_m / 2))
               for name in spec.domains}

    roads = [Road(id="arterial_0", kind="arterial", points=_spine(anchors, brief.region_m, rng),
                  width_m=(spec.arterial_width_m[0] + spec.arterial_width_m[1]) / 2)]
    for block in blocks:
        width = spec.uses[block.use]["road_width_m"]
        kind = "quay" if spec.uses[block.use]["wants_water"] and terrain.distance_to_water_m(*block.centre) < 60 else "local"
        if kind == "quay":
            roads.append(Road(id=f"road_{block.id}", kind="quay",
                              points=((block.x0, block.y0), (block.x1, block.y0), (block.x1, block.y1)),
                              width_m=max(width, spec.local_width_m[1])))
        else:
            roads.append(Road(id=f"road_{block.id}", kind="local",
                              points=((block.x0, block.y0), (block.x1, block.y0)), width_m=width))
    # Rail is built when something in the brief needs it: a works estate always
    # does, a container yard does, a medieval town does not.
    rail_uses = set()
    for requirement in brief.requirements(pack):
        entry = pack.entry(requirement.type)
        if "rail" in entry.needs:
            rail_uses.update(use for use in ROLE_USES.get(entry.role, ()) if use in spec.uses)
    if "industrial" in spec.uses:
        rail_uses.add("industrial")
    if rail_uses:
        yards = sorted((block for block in blocks if block.use in rail_uses), key=lambda block: block.centre)
        if yards:
            # The rail runs through the yards rather than beside them: that is
            # the point of a works estate, and it is what makes "needs rail"
            # satisfiable for every plot instead of only the lucky ones.
            def _outward(block):
                return min(((0.0, block.centre[1]), (brief.region_m, block.centre[1]),
                            (block.centre[0], 0.0), (block.centre[0], brief.region_m)),
                           key=lambda point: math.dist(point, block.centre))
            limit = pack.entry("rail_line").linear_m[1] if "rail_line" in pack.entries else 1200.0
            points = [_outward(yards[0])]
            length = math.dist(points[0], yards[0].centre)
            for yard in yards:
                step = math.dist(points[-1], yard.centre)
                if points[1:] and length + step + math.dist(yard.centre, _outward(yard)) > limit:
                    break
                points.append(yard.centre)
                length += step
            points.append(_outward(yards[len(points) - 2] if len(points) > 1 else yards[0]))
            roads.append(Road(id="rail_0", kind="rail", points=tuple(points), width_m=5.0))
    bridges = []
    for index, road in enumerate(roads):
        bridges.extend(_bridges_for(road, terrain, index))

    sites = _place_sites(brief, pack, terrain, spec, blocks, domains,
                         [road for road in roads if road.kind.startswith("rail")])
    roads.extend(_service_roads(blocks, sites, roads,
                                next((road for road in roads if road.kind == "rail"), None)))
    works = _place_works(brief, pack, terrain, blocks, domains, roads)
    stats = {
        "blocks": len(blocks),
        "blocks_by_use": {use: sum(1 for block in blocks if block.use == use) for use in spec.uses},
        "blocks_by_domain": {domain.id: len(domain.block_ids) for domain in domains},
        "roads": len(roads),
        "arterial_length_m": round(sum(road.length_m for road in roads if road.kind == "arterial"), 1),
        "local_road_length_m": round(sum(road.length_m for road in roads if road.kind in {"local", "quay"}), 1),
        "rail_length_m": round(sum(road.length_m for road in roads if road.kind == "rail"), 1),
        "bridges": len(bridges),
        "sites": len(sites),
        "works": len(works),
        # What the brief asked for and the terrain could not take (work order 014):
        # naming the shortfall is the difference between an infeasible brief and a
        # city that is quietly missing its harbour works.
        "unplaced": _unplaced_requirements(brief, pack, sites, works),
        "sites_by_state": {state: sum(1 for site in sites if site.design_state == state)
                           for state in sorted({site.design_state for site in sites})},
        "works_by_state": {state: sum(1 for work in works if work.design_state == state)
                           for state in sorted({work.design_state for work in works})},
        "arterial_headings_deg": sorted({round(math.degrees(math.atan2(road.points[i + 1][1] - road.points[i][1],
                                                                       road.points[i + 1][0] - road.points[i][0])) % 180, 1)
                                         for road in roads if road.kind == "arterial"
                                         for i in range(len(road.points) - 1)}),
    }
    return SitingPlan(setting=pack.id, seed=brief.seed, region_m=brief.region_m, blocks=blocks,
                      domains=tuple(domains), roads=tuple(roads), bridges=tuple(bridges),
                      sites=tuple(sites), works=tuple(works), stats=stats)


def _unplaced_requirements(brief, pack, sites, works) -> list[dict]:
    """Required landmarks the plan could not place, with what was asked for.

    Work order 014: when the terrain cannot take a demanded type the plan has to
    say so — returning a city that is silently missing a landmark is how a
    feasibility answer turns into a defect.
    """
    def placed(type_name: str) -> int:
        return (sum(1 for site in sites if site.type == type_name)
                + sum(1 for work in works if work.type == type_name))

    return sorted(({"type": requirement.type, "wanted": requirement.count,
                    "placed": placed(requirement.type)}
                   for requirement in brief.requirements(pack)
                   if placed(requirement.type) < requirement.count),
                  key=lambda item: item["type"])


def _place_sites(brief: SceneBrief, pack: SettingPack, terrain: TerrainPlan, spec: DistrictSpec,
                 blocks, domains, rails=()) -> list[Site]:
    """One envelope per demanded building, placed inside a block that suits it."""
    domain_by_name = {domain.id: domain for domain in domains}
    placed: list[Site] = []
    occupied: list[tuple[float, float, float, float]] = []
    requirements = brief.requirements(pack)
    # Adjacency partners are placed first, so a neighbour has something to be
    # next to; otherwise "next to the plaza" is unachievable by construction.
    # Waterfront plots are the scarce ones, so the types that need water are
    # placed before the types that merely prefer space; adjacency partners come
    # first of all because a neighbour needs something to be next to.
    def _priority(item):
        entry = pack.entry(item.type)
        wants_water = bool({"water", "coast"} & set(entry.needs))
        # Anchors first (a plaza has to exist before a hall can stand next to
        # it), then the waterfront plots, ordered big-first because the large
        # water works are the least flexible.
        area = 0.0 if entry.footprint_m2_range is None else sum(entry.footprint_m2_range) / 2
        return (bool(entry.adjacency), not wants_water, -area, -item.count)

    priority = sorted(requirements, key=_priority)
    for requirement in priority:
        entry = pack.entry(requirement.type)
        if entry.footprint_kind == "linear" or entry.role == "vessel":
            # Corridors and vessels are sited by _place_works: a wall crosses
            # many blocks and a ship lies in the water, so neither is a
            # rectangle inside a block.
            continue
        allowed = ROLE_USES.get(entry.role, ("market",))
        candidates = [block for block in blocks if block.use in allowed]
        if entry.role == "vessel" or "water" in entry.needs or "coast" in entry.needs:
            candidates = sorted(candidates, key=lambda block: terrain.distance_to_water_m(*block.centre))
        elif "centre" in entry.needs:
            # A town hall, a hospital or a tower is only "central" if it is near
            # the middle, not merely inside the civic band.
            candidates = sorted(candidates,
                                key=lambda block: math.dist(block.centre, (brief.region_m / 2,) * 2))
        else:
            candidates = sorted(candidates, key=lambda block: -block.area_m2)
        if entry.adjacency:
            partners = [site for site in placed if site.type in entry.adjacency]
            if partners:
                candidates = sorted(candidates,
                                    key=lambda block: min(math.dist(block.centre, partner.centre)
                                                          for partner in partners))
        made = 0
        for block in candidates:
            if made >= requirement.count:
                break
            if terrain.buildable_at(*block.centre) <= 0:
                continue
            domain = domain_by_name[block.domain]
            use_rules = spec.uses[block.use]
            width, depth = _site_footprint(entry, domain, use_rules)
            height, storeys = _site_height(entry, domain, use_rules)
            margin, gap = 6.0, 4.0
            step_x, step_y = width + gap, depth + gap
            usable_x = block.x1 - block.x0 - 2 * margin
            usable_y = block.y1 - block.y0 - 2 * margin
            if usable_x < width or usable_y < depth:
                # The plot cannot hold this building at all. Forcing one cell
                # anyway put a 52 m tower on a 55 m block with 6 m margins and
                # let it hang 3 m over the neighbouring block. Skipping is the
                # honest answer, and the shortfall shows up in
                # `siting.sites_present` (which is what makes the packing in
                # `districts.json` answer for the catalogue's sizes).
                continue
            columns = max(1, int(usable_x // step_x))
            rows = max(1, int(usable_y // step_y))
            cells = [(row, column) for row in range(rows) for column in range(columns)]
            if entry.role == "vessel" or "water" in entry.needs or "coast" in entry.needs:
                # Fill the plot nearest the water first: a wharf shed that ends
                # up 70 m inland is not a wharf shed.
                cells.sort(key=lambda cell: terrain.distance_to_water_m(
                    block.x0 + margin + cell[1] * step_x + width / 2,
                    block.y0 + margin + cell[0] * step_y + depth / 2))
            for row, column in cells:
                if made >= requirement.count:
                    break
                x0 = block.x0 + margin + column * step_x
                y0 = block.y0 + margin + row * step_y
                rect = (x0, y0, x0 + width, y0 + depth)
                if any(_overlap(rect, other, tolerance=0.0) for other in occupied):
                    continue
                centre = ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)
                if terrain.buildable_at(*centre) <= 0 or not _footprint_is_dry(terrain, rect):
                    continue
                # Hard placement filters: a plot that fails its own site needs
                # is not placed at all, rather than placed and reported later.
                if "water" in entry.needs and terrain.distance_to_water_m(*centre) > 60:
                    continue
                if "coast" in entry.needs and terrain.distance_to_water_m(*centre) > 120:
                    continue
                if "centre" in entry.needs and math.dist(centre, (brief.region_m / 2,) * 2) > brief.region_m * 0.4:
                    continue
                if "rail" in entry.needs:
                    gap = min((math.dist(centre, point) for road in rails for point in _sample(road, 12.0)),
                              default=float("inf"))
                    if gap > 150:
                        continue
                occupied.append(rect)
                placed.append(Site(id=f"site_{len(placed):03d}", type=entry.type, role=entry.role,
                                   design_state=entry.design_state, block_id=block.id,
                                   domain_id=block.domain, x0=rect[0], y0=rect[1], x1=rect[2], y1=rect[3],
                                   max_height_m=height, max_storeys=storeys, needs=tuple(entry.needs),
                                   adjacency=tuple(entry.adjacency)))
                made += 1
    return placed


def _overlap(a, b, tolerance: float = 0.0) -> bool:
    return (min(a[2], b[2]) - max(a[0], b[0]) > tolerance
            and min(a[3], b[3]) - max(a[1], b[1]) > tolerance)


def _footprint_is_dry(terrain: TerrainPlan, rect: tuple[float, float, float, float]) -> bool:
    """Check the whole envelope, including its edges, against planned water."""
    x0, y0, x1, y1 = rect
    nx = max(1, math.ceil((x1 - x0) / 2.0))
    ny = max(1, math.ceil((y1 - y0) / 2.0))
    return all(not terrain.water_at(x0 + (x1 - x0) * ix / nx,
                                    y0 + (y1 - y0) * iy / ny)
               for ix in range(nx + 1) for iy in range(ny + 1))


def _service_roads(blocks, sites, network: list[Road], rail: Road | None = None) -> list[Road]:
    """Service lanes between plot rows, plus a connector from each block.

    Without them a plot in the middle of a large block has no street at all,
    and the blocks would not connect to the arterial network.

    Each block joins the **nearest point of the network built so far** instead
    of the nearest point of the arterial. Connecting every block to one distant
    line threw forty long diagonals across the city: measured on the 512 m
    arcane scene (2026-09-27) the network was 19.4 km of street, four to five
    times the reference city's paving, and it read as a grey fan over the map.
    Blocks are ordered by distance so each one attaches to a neighbour, which
    keeps `siting.network_connected` true while the connectors stay local.

    The per-block lane at `y0 + 2` was dropped here as well: the block already
    carries its street along `y0` (`road_<block>`), and two 4 m lanes two metres
    apart paint one wide strip for no gain.
    """
    arterial = next(road for road in network if road.kind == "arterial")
    connected = list(_sample(arterial, step=16.0))
    roads: list[Road] = []
    rows: dict[tuple[str, float], list] = {}
    for site in sites:
        rows.setdefault((site.block_id, round(site.y0, 1)), []).append(site)
    by_id = {block.id: block for block in blocks}
    service: dict[str, list[Road]] = {}
    for (block_id, y0), group in sorted(rows.items()):
        block = by_id[block_id]
        y = round(y0 - 3.0, 2)
        if y <= block.y0:
            y = round(y0 + max(site.y1 for site in group) / 2, 2)
        # Tenths of a metre in the id: two plot rows in one block can round to
        # the same whole metre, and duplicate ids are rejected downstream.
        service.setdefault(block_id, []).append(Road(id=f"service_{block_id}_{int(round(y0 * 10))}",
                                                     kind="local",
                                                     points=((block.x0, y), (block.x1, y)), width_m=3.5))
    order = sorted(blocks, key=lambda block: min(math.dist(block.centre, point) for point in connected))
    for block in order:
        new_roads: list[Road] = []
        # The block's own frontage street is already in the network; sampling it
        # is what lets the next block attach to this one instead of to the
        # arterial across town.
        sample_roads = [road for road in network if road.id == f"road_{block.id}"]
        # A spine down the block ties the frontage, the row lanes and the
        # connector together; without it a plot in the block interior is an
        # island in the graph as well as on the ground.
        centre_x = (block.x0 + block.x1) / 2
        spine = Road(id=f"spine_{block.id}", kind="local",
                     points=((centre_x, block.y0), (centre_x, block.y1)), width_m=3.5)
        new_roads.append(spine)
        sample_roads.append(spine)
        new_roads.extend(service.get(block.id, []))
        sample_roads.extend(service.get(block.id, []))
        if block.use == "industrial":
            # A siding through the yard, joined to the running line: plots reach
            # the rail without crossing half the estate, and the rail network
            # stays in one piece even when the running line is too short to
            # visit every yard on its own.
            points = [(block.x0 + 4.0, block.centre[1]), block.centre, (block.x1 - 4.0, block.centre[1])]
            if rail is not None:
                nearest = min(_sample(rail, step=8.0), key=lambda point: math.dist(point, block.centre))
                points.append(nearest)
            siding = Road(id=f"siding_{block.id}", kind="rail_spur", points=tuple(points), width_m=4.0)
            new_roads.append(siding)
            sample_roads.append(siding)
        nearest = min(connected, key=lambda point: math.dist(point, block.centre))
        if math.dist(block.centre, nearest) > 12.0:
            connector = Road(id=f"connector_{block.id}", kind="local",
                             points=(block.centre, nearest), width_m=5.0)
            new_roads.append(connector)
            sample_roads.append(connector)
        roads.extend(new_roads)
        for road in sample_roads:
            connected.extend(_sample(road, step=16.0))
    return roads


def _work_rects(points, width: float) -> list[tuple[float, float, float, float]]:
    """Axis-aligned rectangles covering a corridor, one per segment."""
    half = width / 2
    return [(min(x0, x1) - half, min(y0, y1) - half, max(x0, x1) + half, max(y0, y1) + half)
            for (x0, y0), (x1, y1) in zip(points, points[1:])]


def _mooring_rect(centre, heading: float, length: float, width: float
                  ) -> tuple[float, float, float, float]:
    """The ship's footprint (its bounding rectangle) where it would lie."""
    cx, cy = centre
    ux, uy = math.cos(heading), math.sin(heading)
    px, py = -uy, ux
    corners = [(cx + ux * length / 2 * along + px * width / 2 * across,
                cy + uy * length / 2 * along + py * width / 2 * across)
               for along in (-1.0, 1.0) for across in (-1.0, 1.0)]
    xs = [corner[0] for corner in corners]
    ys = [corner[1] for corner in corners]
    return (min(xs), min(ys), max(xs), max(ys))


def _rects_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return min(a[2], b[2]) - max(a[0], b[0]) > 1e-6 and min(a[3], b[3]) - max(a[1], b[1]) > 1e-6


def _moor_a_vessel(terrain: TerrainPlan, water, anchor, heading: float, length: float,
                   width: float, works) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Lay a ship alongside the quay without parking it through a pier.

    The first ship in this project was moored by taking the nearest water to a
    harbour block and lying parallel to the shore — which runs the hull straight
    across every pier that juts out from that shore (measured 2026-09-28: the
    hull and the pier corridor overlapped by about 6 x 14 m). A berth is now
    searched for: hold the heading, then step the hull away from the quay and
    along it, and take the first position that clears every work already
    sited. Nothing found means no hull, which is better than a ship inside a
    jetty.
    """
    shore = math.atan2(water[1] - anchor[1], water[0] - anchor[0])
    normal = (math.cos(shore), math.sin(shore))
    axis = (math.cos(heading), math.sin(heading))
    taken = [rect for work in works if work.type in {"pier", "quay_wall"}
             for rect in _work_rects(work.points, work.width_m)]

    def afloat(centre) -> bool:
        # The whole waterline has to be on water: a hull that is half aground is
        # the same defect as a hull inside a jetty, seen from the other side.
        return all(terrain.water_at(centre[0] + axis[0] * offset, centre[1] + axis[1] * offset)
                   for offset in (step * length / 8 - length / 2 for step in range(9)))

    for push in (0.0, 8.0, 16.0, 24.0, 36.0, 48.0, 64.0, 80.0):
        for slide in (0.0, 16.0, -16.0, 32.0, -32.0, 48.0, -48.0, 64.0, -64.0):
            centre = (water[0] + normal[0] * push + axis[0] * slide,
                      water[1] + normal[1] * push + axis[1] * slide)
            if not afloat(centre):
                continue
            rect = _mooring_rect(centre, heading, length, width)
            if any(_rects_overlap(rect, other) for other in taken):
                continue
            return ((centre[0] - axis[0] * length / 2, centre[1] - axis[1] * length / 2),
                    (centre[0] + axis[0] * length / 2, centre[1] + axis[1] * length / 2))
    return None


def _place_works(brief: SceneBrief, pack: SettingPack, terrain: TerrainPlan, blocks, domains,
                 roads) -> list[Work]:
    """Site the linear repertoire: walls, piers, quays, rail and metro lines."""
    works: list[Work] = []
    arterial = next((road for road in roads if road.kind == "arterial"), None)
    rail = next((road for road in roads if road.kind == "rail"), None)
    built = (min(block.x0 for block in blocks), min(block.y0 for block in blocks),
             max(block.x1 for block in blocks), max(block.y1 for block in blocks))
    for requirement in brief.requirements(pack):
        entry = pack.entry(requirement.type)
        if entry.footprint_kind != "linear" and entry.role != "vessel":
            continue
        if entry.role == "vessel":
            # A ship is a long narrow volume on the water, not a plot: derive
            # its length from the declared mooring area.
            area = sum(entry.footprint_m2_range) / 2
            length = round(math.sqrt(area * 6), 1)
            width = round(area / length, 1)
        else:
            length = min(max((entry.linear_m[0] + entry.linear_m[1]) / 2, entry.linear_m[0]), entry.linear_m[1])
            width = (entry.width_m_range[0] + entry.width_m_range[1]) / 2
        for index in range(requirement.count):
            if entry.role == "vessel":
                berths = sorted((block for block in blocks if block.use == "harbour"),
                                key=lambda block: terrain.distance_to_water_m(*block.centre))
                anchor = berths[index % len(berths)].centre if berths else (terrain.region_m / 2,) * 2
                water = _nearest_water(terrain, anchor)
                heading = math.atan2(water[1] - anchor[1], water[0] - anchor[0]) + math.pi / 2
                points = _moor_a_vessel(terrain, water, anchor, heading, length, width, works)
                if points is None:
                    # No clear berth on this stretch of water: skip the hull
                    # rather than park it through a pier.
                    continue
            elif entry.type == "city_wall":
                inset = 6.0 + index * 4.0
                x0, y0, x1, y1 = built[0] - inset, built[1] - inset, built[2] + inset, built[3] + inset
                gate = (x0 + x1) / 2
                points = ((gate, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0), (gate, y0))
            elif entry.type == "quay_wall":
                coast = next((channel for channel in terrain.channels if channel.kind == "coast"), None)
                points = coast.points if coast else _coast_arc(terrain, length)
                points = _clip_to_length(points, entry.linear_m[1])
            elif entry.type == "pier":
                harbour = sorted((block for block in blocks if block.use == "harbour"),
                                 key=lambda block: terrain.distance_to_water_m(*block.centre))
                start = (harbour[index % len(harbour)].centre if harbour else (terrain.region_m / 2,) * 2)
                water = _nearest_water(terrain, start)
                # A pier is as long as the catalogue says: when the water is
                # close, the pier starts further inland instead of shrinking.
                dx, dy = water[0] - start[0], water[1] - start[1]
                span = math.hypot(dx, dy) or 1.0
                land = (water[0] - dx / span * length, water[1] - dy / span * length)
                land = (min(max(land[0], 0.0), terrain.region_m), min(max(land[1], 0.0), terrain.region_m))
                points = (land, water)
            elif entry.type in {"rail_line", "metro_line"}:
                if entry.type == "metro_line" and arterial is not None:
                    points = arterial.points
                elif rail is not None:
                    points = rail.points
                else:
                    points = ((0.0, terrain.region_m * 0.5), (terrain.region_m, terrain.region_m * 0.5))
                # A corridor that stops inside the map is not a line: extend it
                # to the boundary so it leaves the scene the way a road does.
                points = _extend_to_edges(points, terrain.region_m)
            else:
                points = ((terrain.region_m * 0.1, terrain.region_m * (0.3 + 0.1 * index)),
                          (terrain.region_m * 0.9, terrain.region_m * (0.35 + 0.1 * index)))
            length_m = sum(math.dist(points[step], points[step + 1]) for step in range(len(points) - 1))
            if entry.linear_m is not None and length_m < entry.linear_m[0] * 0.6:
                continue
            works.append(Work(id=f"work_{len(works):03d}", type=entry.type, role=entry.role,
                              design_state=entry.design_state, kind=entry.silhouette or "corridor",
                              points=tuple((round(x, 2), round(y, 2)) for x, y in points),
                              width_m=round(width, 2), length_m=round(length_m, 2)))
    return works


def _nearest_water(terrain: TerrainPlan, start) -> tuple[float, float]:
    best = start
    gap = terrain.distance_to_water_m(*start)
    for radius in range(10, 260, 10):
        for angle in range(0, 360, 15):
            point = (start[0] + radius * math.cos(math.radians(angle)),
                     start[1] + radius * math.sin(math.radians(angle)))
            if not (0 <= point[0] <= terrain.region_m and 0 <= point[1] <= terrain.region_m):
                continue
            if terrain.water_at(*point):
                return (round(point[0], 2), round(point[1], 2))
    return (round(best[0], 2), round(best[1], 2))


def _coast_arc(terrain: TerrainPlan, length: float):
    """A fallback coastline arc when the terrain declared no coast channel."""
    points = []
    steps = 12
    for index in range(steps + 1):
        y = terrain.region_m * index / steps
        x = terrain.region_m * (0.2 + 0.6 * abs(math.sin(index / steps * math.pi)))
        points.append((round(x, 2), round(y, 2)))
    return tuple(points)


def _clip_to_length(points, limit: float):
    """Keep the longest contiguous stretch of a corridor within its limit."""
    if len(points) < 2:
        return tuple(points)
    best = points
    best_length = float("inf")
    for start in range(len(points) - 1):
        total = 0.0
        for end in range(start + 1, len(points)):
            total += math.dist(points[end - 1], points[end])
            if total > limit:
                break
            if end - start >= 2:
                candidate = points[start:end + 1]
                if limit - total < best_length:
                    best, best_length = candidate, limit - total
    return tuple(best)


def _extend_to_edges(points, region_m: float):
    """Push the first and last points out to the boundary along their heading."""
    if len(points) < 2:
        return tuple(points)
    result = list(points)
    for index, neighbour in ((0, 1), (-1, -2)):
        start, other = result[index], result[neighbour]
        dx, dy = start[0] - other[0], start[1] - other[1]
        span = math.hypot(dx, dy) or 1.0
        scale = region_m / span
        candidate = (start[0] + dx * scale, start[1] + dy * scale)
        candidate = (min(max(candidate[0], 0.0), region_m), min(max(candidate[1], 0.0), region_m))
        inside = 0 <= start[0] <= region_m and 0 <= start[1] <= region_m
        if inside and (candidate[0] in (0.0, region_m) or candidate[1] in (0.0, region_m)):
            result[index] = (round(candidate[0], 2), round(candidate[1], 2))
    return tuple(result)


def _sample(road: Road, step: float = 8.0):
    points = []
    for index in range(len(road.points) - 1):
        start, end = road.points[index], road.points[index + 1]
        span = math.dist(start, end)
        count = max(1, int(span // step))
        for part in range(count + 1):
            t = part / count
            points.append((start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t))
    return points


def validate_siting(plan: SitingPlan, brief: SceneBrief, pack: SettingPack, terrain: TerrainPlan,
                    spec: DistrictSpec | None = None) -> dict:
    """Independent checks on the finished district plan."""
    spec = spec or load_districts_spec(pack.id, pack.root.parent)
    results = []

    def check(rule: str, passed: bool, message: str, **extra) -> None:
        results.append({"rule": rule, "state": "pass" if passed else "fail", "message": message, **extra})

    covered = sum(block.area_m2 for block in plan.blocks)
    overlap = any(_overlap((a.x0, a.y0, a.x1, a.y1), (b.x0, b.y0, b.x1, b.y1))
                  for index, a in enumerate(plan.blocks) for b in plan.blocks[index + 1:])
    check("siting.blocks_tile", abs(covered - plan.region_m ** 2) < 1.0 and not overlap,
          f"{len(plan.blocks)} blocks cover {round(covered)} m² of {plan.region_m ** 2} m² with no overlap")
    smallest, largest = spec.block_area_m2
    inside = all(smallest * 0.5 <= block.area_m2 <= largest * 1.6 for block in plan.blocks)
    check("siting.block_area", inside,
          f"block areas within {smallest}—{largest} m² (half-size allowed at the edges)")
    # The packing in districts.json has to be able to hold the catalogue it
    # serves: a type whose footprint is bigger than any block could ever be is
    # a data contradiction, and it is cheaper to catch it here than to find a
    # building hanging over its neighbour in the assembled scene.
    too_big = []
    for type_name, entry in pack.entries.items():
        if entry.footprint_kind != "area" or entry.role == "vessel":
            continue
        footprint = sum(entry.footprint_m2_range) / 2
        if footprint > largest * 0.75:
            too_big.append((type_name, round(footprint), largest))
    check("siting.catalogue_fits_blocks", not too_big,
          f"every building fits the largest block ({largest} m²)"
          if not too_big else f"too big for any block: {too_big}")
    for use, rules in spec.uses.items():
        share = sum(1 for block in plan.blocks if block.use == use) / len(plan.blocks)
        low, high = rules["share"]
        check("siting.use_share", low - 0.05 <= share <= high + 0.05,
              f"{use} holds {round(share, 3)} of the blocks, declared {low}—{high}", use=use)
    owned = {block.domain for block in plan.blocks}
    check("siting.domains", owned == set(spec.domains) and all(domain.block_ids for domain in plan.domains),
          f"{len(plan.domains)} domains own every block: {sorted(owned)}")
    # Compare the *applied multiplier*, not the raw mean: a domain full of
    # warehouses would otherwise look taller than a domain of cottages even
    # when its factor is lower. Each site's height divided by its own
    # catalogue midpoint isolates what the domain did to it.
    applied: dict[str, float] = {}
    for domain in plan.domains:
        ratios = []
        for site in plan.sites:
            if site.domain_id != domain.id:
                continue
            entry = pack.entry(site.type)
            if not entry.height_m_range:
                continue
            midpoint = (entry.height_m_range[0] + entry.height_m_range[1]) / 2
            ratios.append(site.max_height_m / midpoint)
        if ratios:
            ratios.sort()
            applied[domain.id] = ratios[len(ratios) // 2]
    for index, first in enumerate(plan.domains):
        for second in plan.domains[index + 1:]:
            if abs(first.height_factor - second.height_factor) < 0.2:
                continue
            if first.id not in applied or second.id not in applied:
                continue
            higher, lower = (first, second) if first.height_factor > second.height_factor else (second, first)
            check("siting.domain_factors_applied", applied[higher.id] >= applied[lower.id] - 0.05,
                  f"{higher.id} applies ×{round(applied[higher.id], 2)} against {lower.id} "
                  f"×{round(applied[lower.id], 2)} (declared {higher.height_factor} vs {lower.height_factor})")

    # Rail is its own network: it meets the streets at loading points, not at
    # every crossing, so folding it into the street graph would hide a genuine
    # break in the streets.
    street_roads = [road for road in plan.roads if not road.kind.startswith("rail")]
    parent = {road.id: road.id for road in street_roads}

    def find(item):
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    samples = {road.id: _sample(road) for road in plan.roads}
    for index, first in enumerate(street_roads):
        for second in street_roads[index + 1:]:
            reach = max(first.width_m, second.width_m) * 1.5 + 4.0
            if any(math.dist(a, b) <= reach for a in samples[first.id] for b in samples[second.id]):
                parent[find(first.id)] = find(second.id)
    roots = {find(road.id) for road in street_roads}
    check("siting.network_connected", len(roots) == 1,
          f"{len(street_roads)} street segments form {len(roots)} connected component(s)")
    rails = [road for road in plan.roads if road.kind.startswith("rail")]
    if rails:
        main_lines = [road for road in rails if road.kind == "rail"]
        ends = (main_lines[0].points[0], main_lines[0].points[-1]) if main_lines else ()
        edge = plan.region_m
        touching = bool(main_lines) and all(
            min(point[0], point[1]) <= 1e-6 or max(point[0], point[1]) >= edge - 1e-6 for point in ends)
        parent = {road.id: road.id for road in rails}
        for index, first in enumerate(rails):
            for second in rails[index + 1:]:
                if any(math.dist(a, b) <= 12.0 for a in samples[first.id] for b in samples[second.id]):
                    parent[find(first.id)] = find(second.id)
        rail_roots = {find(road.id) for road in rails}
        check("siting.rail_connected", len(main_lines) == 1 and touching and len(rail_roots) == 1,
              f"{len(main_lines)} line(s) and {len(rails) - len(main_lines)} siding(s), "
              f"{len(rail_roots)} component(s), ends {ends}")
    for bridge in plan.bridges:
        channel = next(channel for channel in terrain.channels if channel.id == bridge.channel_id)
        midpoint = ((bridge.start[0] + bridge.end[0]) / 2, (bridge.start[1] + bridge.end[1]) / 2)
        inside = _distance_to_channel(*midpoint, channel) <= channel.width_m / 2
        check("siting.bridge_over_water", inside,
              f"{bridge.id} spans {bridge.channel_id} with its deck over the water", bridge=bridge.id)

    for requirement in brief.requirements(pack):
        placed = [site for site in plan.sites if site.type == requirement.type]
        entry = pack.entry(requirement.type)
        if entry.footprint_kind == "linear" or entry.role == "vessel":
            placed = [work for work in plan.works if work.type == requirement.type]
            check("siting.works_present", len(placed) >= requirement.count,
                  f"{requirement.type}: {len(placed)} of {requirement.count} demanded corridors or berths",
                  type=requirement.type)
        else:
            check("siting.sites_present", len(placed) >= requirement.count,
                  f"{requirement.type}: {len(placed)} of {requirement.count} demanded sites", type=requirement.type)
    for work in plan.works:
        entry = pack.entry(work.type)
        if entry.linear_m is None:
            if entry.role != "vessel":
                continue
            # A ship is moored on the water, so "on water" is a requirement
            # rather than the mistake it would be for a shed.
            midpoint = ((work.points[0][0] + work.points[-1][0]) / 2,
                        (work.points[0][1] + work.points[-1][1]) / 2)
            check("siting.work_on_water", terrain.water_at(*midpoint),
                  f"{work.id} ({work.type}) lies in the water", work=work.id)
            continue
        check("siting.work_length", entry.linear_m[0] * 0.6 <= work.length_m <= entry.linear_m[1] * 1.05,
              f"{work.id} ({work.type}) runs {round(work.length_m)} m, catalogue {entry.linear_m}",
              work=work.id)
        if entry.type in {"pier", "quay_wall"}:
            gap = min((terrain.distance_to_water_m(*point) for point in work.points), default=float("inf"))
            check("siting.work_on_water", gap <= 20,
                  f"{work.id} ({work.type}) comes within {round(gap)} m of water", work=work.id)
    for index, first in enumerate(plan.sites):
        rect = (first.x0, first.y0, first.x1, first.y1)
        for second in plan.sites[index + 1:]:
            if _overlap(rect, (second.x0, second.y0, second.x1, second.y1)):
                check("siting.envelopes_disjoint", False, f"{first.id} overlaps {second.id}")
                break
    else:
        check("siting.envelopes_disjoint", True, f"{len(plan.sites)} envelopes do not overlap")
    for site in plan.sites:
        entry = pack.entry(site.type)
        area_ok = entry.footprint_m2_range is None or \
            entry.footprint_m2_range[0] - 1 <= site.area_m2 <= entry.footprint_m2_range[1] + 1
        height_ok = entry.height_m_range is None or \
            entry.height_m_range[0] - 0.5 <= site.max_height_m <= entry.height_m_range[1] + 0.5
        if not (area_ok and height_ok):
            check("siting.envelope_in_catalogue", False,
                  f"{site.id} ({site.type}) is {round(site.area_m2)} m² / {site.max_height_m} m, "
                  f"catalogue says {entry.footprint_m2_range} / {entry.height_m_range}")
            break
    else:
        check("siting.envelope_in_catalogue", True,
              f"every one of {len(plan.sites)} envelopes sits inside its catalogue range")
    off_ground = [site.id for site in plan.sites
                  if terrain.water_at(*site.centre) or terrain.buildable_at(*site.centre) <= 0]
    check("siting.site_on_buildable", not off_ground,
          f"{len(plan.sites) - len(off_ground)} sites on buildable ground" if not off_ground else
          f"unbuildable sites: {off_ground[:5]}")
    wet_footprints = [site.id for site in plan.sites
                      if not _footprint_is_dry(terrain, (site.x0, site.y0, site.x1, site.y1))]
    check("siting.site_footprints_dry", not wet_footprints,
          f"{len(plan.sites) - len(wet_footprints)} site envelopes avoid water" if not wet_footprints else
          f"site envelopes intersect water: {wet_footprints[:5]}")
    for site in plan.sites:
        for need in site.needs:
            if need == "road":
                gap = min(math.dist(site.centre, point) for road in plan.roads if road.kind != "rail"
                          for point in samples[road.id])
                check("siting.needs_road", gap <= 80, f"{site.id} is {round(gap)} m from a street", site=site.id)
            elif need == "water":
                gap = terrain.distance_to_water_m(*site.centre)
                check("siting.needs_water", gap <= 60,
                      f"{site.id} touches water at {round(gap)} m", site=site.id)
            elif need == "coast":
                # "Coast" means on the waterside, not in the water: a transit
                # shed one row behind the quay still counts, a dry dock does
                # not, so the two needs carry different tolerances.
                gap = terrain.distance_to_water_m(*site.centre)
                check("siting.needs_coast", gap <= 120,
                      f"{site.id} is {round(gap)} m from the waterfront", site=site.id)
            elif need == "rail":
                gap = min((math.dist(site.centre, point) for road in rails for point in samples[road.id]),
                          default=float("inf"))
                described = "no rail line at all" if gap == float("inf") else f"{round(gap)} m"
                check("siting.needs_rail", gap <= 150,
                      f"{site.id} is {described} from a rail line or siding", site=site.id)
            elif need == "centre":
                gap = math.dist(site.centre, (plan.region_m / 2, plan.region_m / 2))
                check("siting.needs_centre", gap <= plan.region_m * 0.45,
                      f"{site.id} is {round(gap)} m from the centre", site=site.id)
    for site in plan.sites:
        for partner in site.adjacency:
            if partner not in pack.entries:
                continue
            neighbours = plan.sites_of(partner)
            if not neighbours:
                continue
            gap = min(math.dist(site.centre, other.centre) for other in neighbours)
            check("siting.adjacency", gap <= 220,
                  f"{site.id} is {round(gap)} m from its {partner} neighbour", site=site.id)
    headings = plan.stats["arterial_headings_deg"]
    off_axis = [heading for heading in headings
                if min(abs(heading % 90), 90 - abs(heading % 90)) > 8]
    check("siting.arterial_headings", len(off_axis) >= 2,
          f"{len(off_axis)} of {len(headings)} arterial headings are off the axes: {off_axis[:6]}")
    return {"setting": plan.setting, "state": "pass" if all(r["state"] == "pass" for r in results) else "fail",
            "checks": results, "stats": dict(plan.stats)}
