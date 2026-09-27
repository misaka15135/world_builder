"""Single building design: outline, storeys, rooms, stair, roof (work order 017).

Stage E takes one envelope from stage D and returns the design for that one
building: a stepped outline, the rooms on each storey with the wall between
them, the stair, the entrance, the roof and the furniture - everything inside
the site's maximum footprint and height.

The shape vocabulary is deliberately small (rectangles, per-storey setbacks,
flat / gable / spire roofs) because those are the shapes the target adapters
already export and the shapes whose rules have been verified in the game. What
changes per type is the *policy*: how many storeys, which rooms they hold, what
furniture, which roof. That policy lives in `settings/<id>/designs.json`, so a
new building type is data plus a template entry, not new geometry code.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

from .catalogue import DEFAULT_SETTINGS_ROOT, SceneError, SettingPack
from .siting import Site

DESIGN_VERSION = "0.1.0"
ROOF_STYLES = ("flat", "gable", "spire")
ENTRY_SIDES = ("north", "south", "east", "west")
# Entrance geometry the design hands to the target adapters: a 2.0 m door in a
# 2.4 m opening. `DOOR_SPAN_MIN_M` is the shortest face that can hold it (1.0 m
# jamb + 2.0 m door + a 0.3 m corner margin); a face that cannot hold it hands
# the entrance to the longest face instead.
ENTRY_DOOR_M = 2.0
ENTRY_HEIGHT_M = 2.4
DOOR_SPAN_MIN_M = 3.31
# 2.8 m stays the squeeze floor: a 2.4 m door plus the floor slab needs 2.7 m,
# and the test suite pins "squeeze the storeys, do not drop them" for a tight
# envelope. A storey too short for the quantised opening is handled on the
# target side by carving the doorway through the ground slab (adapter 0.1.0-city.6).
MIN_STOREY_M = 2.8
# Furniture per room use: a small vocabulary with sizes in metres. Stage E
# places it; stage F and the target adapters only read it.
FURNITURE = {
    "hearth": [("hearth", (1.6, 1.0, 1.0))],
    "bed": [("bed", (1.0, 2.0, 0.6))],
    "store": [("crate", (1.0, 1.0, 1.0))],
    "counter": [("counter", (2.0, 0.8, 1.0)), ("crate", (1.0, 1.0, 1.0))],
    "stall": [("table", (1.6, 0.8, 0.9))],
    "workbench": [("workbench", (1.8, 0.9, 0.9)), ("anvil", (0.8, 0.8, 0.8))],
    "shelf": [("shelf", (2.2, 0.8, 1.8)), ("table", (1.6, 0.8, 0.9))],
    "reading_table": [("table", (2.0, 1.0, 0.9)), ("chair", (0.6, 0.6, 0.9))],
    "nave": [("pew", (2.5, 0.8, 0.9))],
    "vestry": [("cabinet", (1.2, 0.8, 1.6))],
    "council_chamber": [("long_table", (3.0, 1.2, 0.9))],
    "records_room": [("shelf", (2.2, 0.8, 1.8))],
    "task_board": [("board", (2.0, 0.3, 1.4)), ("table", (1.6, 0.8, 0.9))],
    "dormitory": [("bed", (1.0, 2.0, 0.6))],
    "taproom": [("counter", (2.2, 0.8, 1.0)), ("crate", (1.0, 1.0, 1.0))],
    "guest_room": [("bed", (1.0, 2.0, 0.6))],
    "open_plan": [("desk", (1.6, 0.9, 0.9))],
    "meeting_room": [("long_table", (3.0, 1.2, 0.9))],
    "kitchen": [("counter", (2.0, 0.8, 1.0))],
    "ward": [("bed", (1.0, 2.0, 0.6))],
    "consulting": [("desk", (1.6, 0.9, 0.9))],
    "classroom": [("desk", (1.6, 0.9, 0.9))],
    "staff_room": [("table", (1.6, 0.8, 0.9))],
    "office": [("desk", (1.6, 0.9, 0.9)), ("shelf", (2.0, 0.8, 1.6))],
    "lobby": [("reception", (2.4, 0.9, 1.1))],
    "machine_hall": [("machine", (3.0, 2.0, 2.0))],
    "storage": [("crate", (1.0, 1.0, 1.0)), ("pallet", (1.2, 1.2, 0.3))],
    "loading": [("pallet", (1.2, 1.2, 0.3))],
    "customs_hall": [("counter", (2.4, 0.9, 1.0))],
    "watch_room": [("desk", (1.6, 0.9, 0.9))],
    "lamp_room": [("lamp", (1.2, 1.2, 1.2))],
}
ROOM_USES = tuple(FURNITURE)


@dataclass(frozen=True)
class DesignTemplate:
    type: str
    kind: str = "building"
    storeys: tuple[int, int] | None = None
    storey_height_m: float | None = None
    roof: str | None = None
    roof_height_m: float | None = None
    setback_m: float | None = None
    stair: str | None = None
    room_uses: tuple[tuple[str, ...], ...] | None = None
    aspect: float | None = None
    # `kind: "open_space"` (work order 017 class 2): a plaza or a park is a
    # surface, not a building — paving, one path across it, and fixed furniture.
    paving: str | None = None
    path_token: str | None = None
    fixtures: tuple[str, ...] = ()


OPEN_SPACE_PAVING = ("stone", "path", "gravel")
# `crate` and `stack` are the yard vocabulary: a freight yard stacks pallets, a
# container yard stacks boxes, and both are surface plans rather than buildings.
OPEN_SPACE_FIXTURES = ("lamp", "bench", "tree", "planter", "crate", "stack")


@dataclass(frozen=True)
class OpenSpaceDesign:
    """A ground plan: paving, a path and fixtures, with no storeys at all."""

    id: str
    type: str
    role: str
    design_state: str
    site_id: str
    x0: float
    y0: float
    x1: float
    y1: float
    entry_side: str
    paving: str
    path_token: str
    path: tuple[float, float, float, float]
    fixtures: tuple[dict, ...]
    height_m: float = 1.0

    @property
    def area_m2(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)

    def to_dict(self) -> dict:
        return {
            "design_version": DESIGN_VERSION,
            "id": self.id, "type": self.type, "role": self.role, "design_state": self.design_state,
            "site_id": self.site_id, "kind": "open_space",
            "outline": [round(self.x0, 3), round(self.y0, 3), round(self.x1, 3), round(self.y1, 3)],
            "height_m": round(self.height_m, 3), "paving": self.paving,
            "path": {"token": self.path_token,
                     "rect": [round(value, 3) for value in self.path]},
            "fixtures": [dict(item) for item in self.fixtures],
        }


def parse_designs(payload: dict, setting: str) -> dict:
    code = "designs.spec"
    if not isinstance(payload, dict) or set(payload) != {"designs_version", "setting", "templates"}:
        raise SceneError(code, "designs.json must contain designs_version, setting and templates")
    if payload["designs_version"] != DESIGN_VERSION:
        raise SceneError(code, f"designs_version must be {DESIGN_VERSION}")
    if payload["setting"] != setting:
        raise SceneError(code, f"designs.json belongs to {payload['setting']!r}, loaded as {setting!r}")
    templates = payload["templates"]
    if not isinstance(templates, dict) or not templates:
        raise SceneError(code, "templates must be a nonempty mapping")
    parsed = {}
    for type_name, raw in templates.items():
        if isinstance(raw, dict) and raw.get("kind") == "open_space":
            keys = {"kind", "paving", "path", "fixtures"}
            if set(raw) != keys:
                raise SceneError(code, f"{type_name} must contain exactly {', '.join(sorted(keys))}")
            if raw["paving"] not in OPEN_SPACE_PAVING or raw["path"] not in OPEN_SPACE_PAVING:
                raise SceneError(code, f"{type_name}: paving and path must be one of "
                                       f"{', '.join(OPEN_SPACE_PAVING)}")
            fixtures = raw["fixtures"]
            if not isinstance(fixtures, list) or any(item not in OPEN_SPACE_FIXTURES for item in fixtures):
                raise SceneError(code, f"{type_name}.fixtures must list "
                                       f"{', '.join(OPEN_SPACE_FIXTURES)}")
            parsed[type_name] = DesignTemplate(type=type_name, kind="open_space", paving=raw["paving"],
                                               path_token=raw["path"], fixtures=tuple(fixtures))
            continue
        keys = {"storeys", "storey_height_m", "roof", "roof_height_m", "setback_m", "stair",
                "room_uses", "aspect"}
        if not isinstance(raw, dict) or set(raw) != keys:
            raise SceneError(code, f"{type_name} must contain exactly {', '.join(sorted(keys))}")
        storeys = raw["storeys"]
        if not isinstance(storeys, list) or len(storeys) != 2 or storeys[0] < 1 or storeys[0] > storeys[1]:
            raise SceneError(code, f"{type_name}.storeys must be an ascending pair of positive integers")
        if raw["roof"] not in ROOF_STYLES:
            raise SceneError(code, f"{type_name}.roof must be one of {', '.join(ROOF_STYLES)}")
        if raw["stair"] not in ("straight", "none"):
            raise SceneError(code, f"{type_name}.stair must be straight or none")
        if not 2.4 <= raw["storey_height_m"] <= 6:
            raise SceneError(code, f"{type_name}.storey_height_m must be 2.4—6 m")
        if raw["setback_m"] < 0 or raw["aspect"] <= 0:
            raise SceneError(code, f"{type_name} needs a nonnegative setback and a positive aspect")
        plan = raw["room_uses"]
        if not isinstance(plan, list) or not plan or any(not isinstance(row, list) or not row for row in plan):
            raise SceneError(code, f"{type_name}.room_uses must list the rooms of each storey")
        for row in plan:
            for use in row:
                if use not in FURNITURE:
                    raise SceneError(code, f"{type_name}: unknown room use {use!r}")
        parsed[type_name] = DesignTemplate(type=type_name, storeys=(storeys[0], storeys[1]),
                                           storey_height_m=float(raw["storey_height_m"]),
                                           roof=raw["roof"], roof_height_m=float(raw["roof_height_m"]),
                                           setback_m=float(raw["setback_m"]), stair=raw["stair"],
                                           room_uses=tuple(tuple(row) for row in plan),
                                           aspect=float(raw["aspect"]))
    return parsed


def load_designs(setting: str, root: Path | str = DEFAULT_SETTINGS_ROOT) -> dict:
    path = Path(root) / setting / "designs.json"
    if not path.is_file():
        raise SceneError("designs.spec_missing", f"{setting} has no designs.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SceneError("designs.spec_read", f"cannot read {path}: {exc}") from exc
    return parse_designs(payload, setting)


@dataclass(frozen=True)
class Room:
    id: str
    use: str
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class Storey:
    index: int
    x0: float
    y0: float
    x1: float
    y1: float
    z_m: float
    rooms: tuple[Room, ...]
    partition_x_m: float | None


@dataclass(frozen=True)
class Furniture:
    id: str
    use: str
    room_id: str
    x0: float
    y0: float
    height_m: float


@dataclass(frozen=True)
class BuildingDesign:
    id: str
    type: str
    role: str
    design_state: str
    site_id: str
    x0: float
    y0: float
    x1: float
    y1: float
    storeys: tuple[Storey, ...]
    storey_height_m: float
    roof: str
    roof_height_m: float
    entry_side: str
    entry_offset_m: float
    entry_width_m: float
    entry_height_m: float
    stair: dict | None
    furniture: tuple[Furniture, ...]
    materials: dict
    height_m: float

    @property
    def centre(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    @property
    def area_m2(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)

    def to_dict(self) -> dict:
        return {
            "design_version": DESIGN_VERSION,
            "id": self.id, "type": self.type, "role": self.role, "design_state": self.design_state,
            "site_id": self.site_id,
            "outline": [self.x0, self.y0, self.x1, self.y1],
            "storey_height_m": self.storey_height_m, "roof": self.roof, "roof_height_m": self.roof_height_m,
            "height_m": round(self.height_m, 2),
            "storeys": [{"index": storey.index, "rect": [storey.x0, storey.y0, storey.x1, storey.y1],
                         "z_m": storey.z_m, "partition_x_m": storey.partition_x_m,
                         "rooms": [{"id": room.id, "use": room.use,
                                    "rect": [room.x0, room.y0, room.x1, room.y1]} for room in storey.rooms]}
                        for storey in self.storeys],
            "entry": {"side": self.entry_side, "offset_m": self.entry_offset_m,
                      "width_m": self.entry_width_m, "height_m": self.entry_height_m},
            "stair": self.stair,
            "furniture": [{"id": item.id, "use": item.use, "room": item.room_id,
                           "x0": item.x0, "y0": item.y0, "height_m": item.height_m}
                          for item in self.furniture],
            "materials": dict(self.materials),
        }


def _insets(width: float, depth: float, storeys: int, setback_m: float) -> list[tuple[float, float, float, float]]:
    """Per-storey insets (west, east, south, north), ground storey flush.

    The stair strip runs along the east side, so the east edge never moves; the
    other three step back by whole metres, capped so the rooms keep their floor
    space. This is the same shape rule the 512 m template settled on after the
    stepped roofs turned out to be a lid on a box.
    """
    insets = [(0.0, 0.0, 0.0, 0.0) for _ in range(storeys)]
    if storeys < 3 or setback_m <= 0:
        return insets
    cap = min(setback_m, width - 9.0, depth / 2 - 3.0)
    step = math.floor(max(0.0, cap))
    if step >= 1:
        insets[-1] = (step, 0.0, step, step)
    return insets


def design_building(site: Site, entry, pack: SettingPack, template: DesignTemplate, *,
                    entry_side: str = "east", seed: int = 1,
                    storeys: int | None = None) -> BuildingDesign:
    """Design one building inside the site's envelope."""
    if entry_side not in ENTRY_SIDES:
        raise SceneError("design.entry_side", f"unknown entry side {entry_side!r}")
    width_span = site.x1 - site.x0
    depth_span = site.y1 - site.y0
    # A door needs about six metres of wall. On a narrow plot the entrance moves
    # to the side that can actually take one, instead of being declared on a
    # face too short to hold it (the target adapter rejects the latter, and it
    # was a narrow scene building that failed exactly so).
    if entry_side in {"north", "south"} and width_span < 6.0 and depth_span >= 6.0:
        entry_side = "east"
    elif entry_side in {"east", "west"} and depth_span < 6.0 and width_span >= 6.0:
        entry_side = "south"
    spans = {"north": width_span, "south": width_span, "east": depth_span, "west": depth_span}
    # A 2.0 m door needs a 1.0 m jamb, the 2.0 m opening and a 0.3 m corner
    # margin: a face shorter than 3.3 m cannot carry it, and the target adapter
    # rejects such a shell outright. Denser plots reached that case on
    # 2026-09-27 (site_063), so the entrance moves to the longest face.
    if spans[entry_side] < DOOR_SPAN_MIN_M:
        entry_side = max(spans, key=lambda side: spans[side])
    along_span = spans[entry_side]
    entry_offset = max(1.0, min(0.3 * along_span, along_span - ENTRY_DOOR_M - 0.31))
    fingerprint = f"{site.id}:{entry.type}:{seed}:{DESIGN_VERSION}".encode("utf-8")
    rng = random.Random(int.from_bytes(hashlib.sha256(fingerprint).digest()[:8], "big"))
    width = site.x1 - site.x0
    depth = site.y1 - site.y0
    chosen = storeys if storeys is not None else rng.randint(*template.storeys)
    chosen = max(1, min(chosen, site.max_storeys, template.storeys[1]))
    storey_height = template.storey_height_m
    if template.stair == "none":
        # A template without a stair is a single-storey shell: building a second
        # storey with no way up would be a defect, not a design. Where the
        # catalogue asks for a hall taller than the template's storey height,
        # the single storey simply has a higher ceiling.
        chosen = 1
        if entry.height_m_range:
            storey_height = max(storey_height,
                                min(site.max_height_m - template.roof_height_m,
                                    max(entry.height_m_range[0] - template.roof_height_m, storey_height)))
    fewest = 1
    if entry.height_m_range:
        low, high = entry.height_m_range
        # The catalogue's height range is the contract, so the storey count is
        # chosen to land inside it rather than wherever the template's own
        # range happens to fall.
        fewest = max(1, math.ceil((low - template.roof_height_m) / template.storey_height_m))
        most = max(fewest, math.floor((high - template.roof_height_m) / template.storey_height_m))
        if template.stair != "none":
            chosen = max(fewest, min(chosen, most))
    height = chosen * storey_height + template.roof_height_m
    if height > site.max_height_m + 1e-6:
        # Fit the envelope instead of overflowing it. Lowering the ceilings is
        # preferred to dropping a storey, because the catalogue's height range
        # is a contract and a squashed two-storey house is still a house.
        squeezed = (site.max_height_m - template.roof_height_m) / chosen
        # MIN_STOREY_M is the floor, not 2.6: a 2.4 m door plus the floor slab
        # needs 2.7 m before quantisation, and the adapter's block-quantised
        # lintel needs 3.0 m, so a squeezed storey below that has no room for its
        # own entrance (one town hall was rejected by the adapter exactly so).
        if chosen >= fewest and squeezed >= MIN_STOREY_M:
            # Round the ceiling *down* to the millimetre: rounding to nearest
            # pushed one tower 2 mm past its envelope, and the envelope is hard.
            storey_height = math.floor(squeezed * 1000) / 1000
        else:
            while chosen > 1 and chosen * storey_height + template.roof_height_m > site.max_height_m:
                chosen -= 1
            squeezed = (site.max_height_m - template.roof_height_m) / chosen
            storey_height = math.floor(max(MIN_STOREY_M, min(storey_height, squeezed)) * 1000) / 1000
        height = chosen * storey_height + template.roof_height_m
    insets = _insets(width, depth, chosen, template.setback_m)
    stair_void = 3.0
    room_span = max(4.0, width - stair_void - 4.0)
    storeys_out = []
    furniture = []
    for index in range(chosen):
        west, east, south, north = insets[index]
        x0, y0 = site.x0 + west, site.y0 + south
        x1, y1 = site.x1 - east, site.y1 - north
        uses = template.room_uses[index % len(template.room_uses)]
        uses = uses[:2] if len(uses) >= 2 else (uses[0], uses[0])
        mid = (y0 + y1) / 2
        block_x0, block_x1 = x0 + 1.0, x1 - stair_void - 1.0
        rooms = []
        for room_index, (n0, n1) in enumerate(((y0 + 1.0, mid - 0.5), (mid + 0.5, y1 - 1.0))):
            room = Room(id=f"{site.id}_s{index}_r{room_index}", use=uses[room_index],
                        x0=round(block_x0, 3), y0=round(n0, 3), x1=round(block_x1, 3), y1=round(n1, 3))
            rooms.append(room)
            for item_index, (use, (item_w, item_d, item_h)) in enumerate(FURNITURE[room.use]):
                room_w = room.x1 - room.x0
                room_d = room.y1 - room.y0
                ox = min(1.0, max(0.2, room_w - item_w - 0.2))
                on = min(1.0 + 2.0 * item_index, max(0.2, room_d - item_d - 0.2))
                furniture.append(Furniture(id=f"{room.id}_f{item_index}", use=use, room_id=room.id,
                                           x0=round(room.x0 + ox, 3), y0=round(room.y0 + on, 3),
                                           height_m=item_h))
        storeys_out.append(Storey(index=index, x0=round(x0, 3), y0=round(y0, 3), x1=round(x1, 3),
                                  y1=round(y1, 3), z_m=round(index * storey_height, 3),
                                  rooms=tuple(rooms), partition_x_m=round(block_x0, 3)))
    stair = None
    if chosen >= 2 and template.stair == "straight":
        ground = storeys_out[0]
        # The reservation has to sit strictly inside the shell: a void that
        # reaches the outer face is not a stairwell, and the target adapter
        # rejects it (a 2-storey scene building was rejected exactly so).
        # The void has to hold the *whole flight* as well, not just its clear
        # width: the adapter checks the stair box against the reservation, and a
        # 6.85 m deep harbour building had the flight overhang it by 1.15 m
        # (2026-09-27). Front margin, run, landing and rear margin all live
        # inside the outline, so the margins give way first and the run follows.
        depth = ground.y1 - ground.y0
        # 3 + 2 + 3 = 8 m is what the roomier front margin needs; below that the
        # margins shrink to 1 m so the reservation still fits with a 2 m run.
        front, landing = (3.0, 2.0) if depth >= 8.0 else (1.0, 1.0)
        run = max(2.0, min(8.0 if width >= 14 else 4.0, depth - front - landing - 1.0))
        void_x0 = ground.x1 - stair_void - 1.0
        void_x1 = ground.x1 - 1.0
        void_y0 = ground.y0 + front
        void_y1 = void_y0 + run + landing
        stair = {"representation": "straight_stair", "side": "east",
                 "x0": round(void_x0, 3), "y0": round(void_y0, 3),
                 "width_m": 2.0, "run_m": run, "rise_m": storey_height, "steps": 20,
                 "landing_m": landing, "void": [round(void_x0, 3), round(void_x1, 3),
                                                round(void_y0, 3), round(void_y1, 3)]}
    return BuildingDesign(id=f"design_{site.id}", type=entry.type, role=entry.role,
                           design_state=entry.design_state, site_id=site.id,
                           # Rounded to the same millimetre grid as the storey
                           # outlines: a footprint rounded down with a storey
                           # rounded up would put the storey outside its own
                           # site, which is how this check first failed.
                           x0=round(site.x0, 3), y0=round(site.y0, 3),
                           x1=round(site.x1, 3), y1=round(site.y1, 3),
                           storeys=tuple(storeys_out), storey_height_m=round(storey_height, 3),
                           roof=template.roof, roof_height_m=template.roof_height_m,
                           entry_side=entry_side, entry_offset_m=round(entry_offset, 3),
                           entry_width_m=ENTRY_DOOR_M,
                           entry_height_m=ENTRY_HEIGHT_M, stair=stair, furniture=tuple(furniture),
                           materials=dict(pack.materials), height_m=round(height, 3))


def _even_spans(low: float, high: float, step: float) -> list[float]:
    """Evenly spaced fixture positions strictly inside [low, high]."""
    if high - low < 1.0:
        return []
    count = max(1, int((high - low) // step))
    return [round(low + (high - low) * index / max(count, 1), 3) for index in range(count + 1)
            if low + (high - low) * index / max(count, 1) <= high]


def _fixture(fixture_id: str, use: str, x: float, y: float, height_m: float = 1.0) -> dict:
    """One 1 m fixture footprint, anchored on its centre."""
    return {"id": fixture_id, "use": use, "x0": round(x - 0.5, 3), "y0": round(y - 0.5, 3),
            "x1": round(x + 0.5, 3), "y1": round(y + 0.5, 3), "height_m": round(height_m, 3)}


def design_open_space(site: Site, template: DesignTemplate, *, entry_side: str = "south",
                      fixture_cap: int = 24) -> OpenSpaceDesign:
    """A plaza or a park: paving, one path from the street, fixed furniture.

    The source declares surfaces, not blocks: the paving and path tokens name a
    material family and the target picks the block. Fixtures are laid by rule —
    lamps on the perimeter, benches one row inboard of the street side and trees
    on a grid — so two runs of the same input give the same plan.
    """
    if entry_side not in ENTRY_SIDES:
        raise SceneError("design.entry_side", f"unknown entry side {entry_side!r}")
    if template.kind != "open_space":
        raise SceneError("design.kind", f"{template.type} is not an open space template")
    x0, y0, x1, y1 = site.x0, site.y0, site.x1, site.y1
    # The catalogue's envelope for a plaza or a park can be as low as 0.6 m, so
    # the fixtures rise to whatever the site allows instead of assuming a metre.
    height = max(0.2, min(1.0, float(site.max_height_m)))
    # A `green` block's height factor can squeeze a park's envelope to 0.2 m,
    # which no fixture fits in. The paving still is a park; the furniture waits
    # for a taller envelope (the siting data is the lever, recorded in 016).
    wants_fixtures = float(site.max_height_m) >= 0.4
    if entry_side in {"north", "south"}:
        centre = (x0 + x1) / 2
        path = (centre - 1.0, y0, centre + 1.0, y1)
    else:
        centre = (y0 + y1) / 2
        path = (x0, centre - 1.0, x1, centre + 1.0)
    fixtures: list[dict] = []
    if wants_fixtures and "lamp" in template.fixtures:
        for index, x in enumerate(_even_spans(x0 + 1.5, x1 - 1.5, 8.0)):
            fixtures.append(_fixture(f"{site.id}_lamp_s{index}", "lamp", x, y0 + 1.5, height))
            fixtures.append(_fixture(f"{site.id}_lamp_n{index}", "lamp", x, y1 - 1.5, height))
        for index, y in enumerate(_even_spans(y0 + 1.5, y1 - 1.5, 8.0)):
            fixtures.append(_fixture(f"{site.id}_lamp_w{index}", "lamp", x0 + 1.5, y, height))
            fixtures.append(_fixture(f"{site.id}_lamp_e{index}", "lamp", x1 - 1.5, y, height))
    if wants_fixtures and "bench" in template.fixtures:
        for index, x in enumerate(_even_spans(x0 + 3.0, x1 - 3.0, 6.0)):
            fixtures.append(_fixture(f"{site.id}_bench{index}", "bench", x, y0 + 3.5, height))
    if wants_fixtures and "tree" in template.fixtures:
        for row, y in enumerate(_even_spans(y0 + 4.0, y1 - 4.0, 6.0)):
            for col, x in enumerate(_even_spans(x0 + 4.0, x1 - 4.0, 6.0)):
                if len(fixtures) >= fixture_cap:
                    break
                fixtures.append(_fixture(f"{site.id}_tree{row}_{col}", "tree", x, y, height))
    # Yards stack their goods in rows: crates and containers follow the same
    # grid the trees use, spaced by their own step, so a freight yard or a
    # container yard reads as stacks rather than scattered objects.
    for token, step in (("crate", 5.0), ("stack", 6.0)):
        if not wants_fixtures or token not in template.fixtures:
            continue
        for row, y in enumerate(_even_spans(y0 + 4.0, y1 - 4.0, step)):
            for col, x in enumerate(_even_spans(x0 + 4.0, x1 - 4.0, step)):
                if len(fixtures) >= fixture_cap:
                    break
                fixtures.append(_fixture(f"{site.id}_{token}{row}_{col}", token, x, y, height))
    return OpenSpaceDesign(id=f"design_{site.id}", type=template.type, role=site.role,
                           design_state=site.design_state, site_id=site.id,
                           x0=round(x0, 3), y0=round(y0, 3), x1=round(x1, 3), y1=round(y1, 3),
                           entry_side=entry_side, paving=template.paving,
                           path_token=template.path_token,
                           path=tuple(round(value, 3) for value in path),
                           fixtures=tuple(fixtures[:fixture_cap]), height_m=round(height, 3))


def validate_open_space(design: OpenSpaceDesign, site: Site) -> dict:
    """Independent checks on a ground plan: inside the site, low, reachable."""
    results: list[dict] = []

    def check(rule: str, passed: bool, message: str) -> None:
        results.append({"rule": rule, "state": "pass" if passed else "fail", "message": message})

    # Design coordinates live on the millimetre grid (a rounded outline can land
    # 1 mm outside the site's own value), so containment is checked that way.
    check("design.outline", site.x0 - 2e-3 <= design.x0 and design.x1 <= site.x1 + 2e-3
          and site.y0 - 2e-3 <= design.y0 and design.y1 <= site.y1 + 2e-3,
          f"paving {round(design.area_m2)} m² inside the site")
    check("design.height", design.height_m <= site.max_height_m + 2e-3,
          f"{design.height_m} m against the envelope {site.max_height_m} m")
    check("design.fixtures_inside",
          all(design.x0 - 2e-3 <= item["x0"] and item["x1"] <= design.x1 + 2e-3
              and design.y0 - 2e-3 <= item["y0"] and item["y1"] <= design.y1 + 2e-3
              for item in design.fixtures),
          f"{len(design.fixtures)} fixture(s) inside the paving")
    px0, py0, px1, py1 = design.path
    touches = (abs(py0 - design.y0) < 1e-6 and design.entry_side == "south"
               or abs(py1 - design.y1) < 1e-6 and design.entry_side == "north"
               or abs(px0 - design.x0) < 1e-6 and design.entry_side == "west"
               or abs(px1 - design.x1) < 1e-6 and design.entry_side == "east")
    check("design.path_reaches_street", touches,
          f"the path starts on the {design.entry_side} edge")
    check("design.tokens", design.paving in OPEN_SPACE_PAVING and design.path_token in OPEN_SPACE_PAVING,
          f"paving {design.paving!r}, path {design.path_token!r}")
    return {"design_id": design.id, "type": design.type, "kind": "open_space",
            "state": "pass" if all(item["state"] == "pass" for item in results) else "fail",
            "checks": results}


def design(site: Site, entry, pack: SettingPack, template: DesignTemplate, *,
           entry_side: str = "east", seed: int = 1):
    """Stage E entry point: a building design or a ground plan, by template kind."""
    if template.kind == "open_space":
        return design_open_space(site, template, entry_side=entry_side)
    return design_building(site, entry, pack, template, entry_side=entry_side, seed=seed)


def validate_design(design: BuildingDesign, site: Site, entry) -> dict:
    """Independent checks on one finished design."""
    results = []
    # Design coordinates are stored to the millimetre, so containment is judged
    # on that grid rather than with a floating-point epsilon.
    tolerance = 2e-3

    def check(rule: str, passed: bool, message: str) -> None:
        results.append({"rule": rule, "state": "pass" if passed else "fail", "message": message})

    inside = (design.x0 >= site.x0 - tolerance and design.x1 <= site.x1 + tolerance
              and design.y0 >= site.y0 - tolerance and design.y1 <= site.y1 + tolerance)
    fits_envelope = (inside and design.area_m2 <= site.area_m2 + 1.0
                     and design.height_m <= site.max_height_m + 1e-6
                     and len(design.storeys) <= site.max_storeys)
    check("design.envelope", fits_envelope,
          f"{design.id} is {round(design.area_m2)} m² / {design.height_m} m inside "
          f"{round(site.area_m2)} m² / {site.max_height_m} m / {site.max_storeys} storeys")
    outline_ok = all(storey.x0 >= design.x0 - tolerance and storey.x1 <= design.x1 + tolerance
                     and storey.y0 >= design.y0 - tolerance and storey.y1 <= design.y1 + tolerance
                     and storey.x1 - storey.x0 > 4 and storey.y1 - storey.y0 > 4
                     for storey in design.storeys)
    check("design.storey_outline", outline_ok, f"{len(design.storeys)} storey outline(s) inside the footprint")
    ground, first = design.storeys[0], design.storeys[-1]
    check("design.setback", abs(ground.x0 - design.x0) < tolerance and abs(ground.y0 - design.y0) < tolerance
          and first.x0 >= ground.x0 - tolerance and first.y0 >= ground.y0 - tolerance
          and first.x1 <= ground.x1 + tolerance,
          "the ground storey keeps the footprint and upper storeys step back, never out")
    for storey in design.storeys:
        rooms = storey.rooms
        check("design.rooms_inside", len(rooms) == 2
              and all(room.x0 >= storey.x0 and room.x1 <= storey.x1
                      and room.y0 >= storey.y0 and room.y1 <= storey.y1 for room in rooms),
              f"storey {storey.index}: two rooms inside the storey outline")
        if len(rooms) == 2:
            gap = rooms[1].y0 - rooms[0].y1
            check("design.partition", abs(gap - 1.0) < 1e-6,
                  f"storey {storey.index}: a 1 m partition slot divides the two rooms")
        if design.stair:
            void = design.stair["void"]
            check("design.stair_void", all(not (room.x0 < void[1] and room.x1 > void[0]
                                                and room.y0 < void[3] and room.y1 > void[2]) for room in rooms),
                  f"storey {storey.index}: rooms clear the stair reservation")
            # The target adapter checks the flight against its reservation, so
            # the source has to hold that invariant itself: a 6.85 m deep
            # harbour building shipped a flight that overhung the void by
            # 1.15 m and only the export caught it (2026-09-27).
            run_end = design.stair["y0"] + design.stair["run_m"] + design.stair["landing_m"]
            check("design.stair_fits_void",
                  void[0] - 1e-6 <= design.stair["x0"]
                  and design.stair["x0"] + design.stair["width_m"] <= void[1] + 1e-6
                  and void[2] - 1e-6 <= design.stair["y0"] and run_end <= void[3] + 1e-6,
                  f"storey {storey.index}: the flight and its landing fit the reservation")
    if len(design.storeys) >= 2:
        check("design.stair", design.stair is not None
              and design.stair["rise_m"] > 0 and design.stair["width_m"] >= 1.2,
              "a multi-storey building has a stair that reaches the first upper floor")
    else:
        check("design.stair", design.stair is None, "a single-storey building has no stair")
    check("design.entry", design.entry_side in ENTRY_SIDES and design.entry_width_m >= 1.0
          and design.entry_height_m >= 2.0 and design.entry_offset_m >= 1.0,
          f"entrance on the {design.entry_side} side, {design.entry_width_m}×{design.entry_height_m} m")
    rooms_by_id = {room.id: room for storey in design.storeys for room in storey.rooms}
    furniture_ok = all(item.room_id in rooms_by_id
                       and item.x0 >= rooms_by_id[item.room_id].x0 - 1e-6
                       and item.y0 >= rooms_by_id[item.room_id].y0 - 1e-6
                       and item.x0 + 2.0 <= rooms_by_id[item.room_id].x1 + 1.0
                       and item.y0 + 2.0 <= rooms_by_id[item.room_id].y1 + 1.0
                       for item in design.furniture)
    check("design.furniture", furniture_ok,
          f"{len(design.furniture)} piece(s) of furniture inside their rooms")
    check("design.materials", bool(design.materials)
          and {"shell", "floor", "roof"} <= set(design.materials),
          f"materials from the background: {sorted(design.materials)}")
    if entry.height_m_range:
        check("design.height_in_catalogue", entry.height_m_range[0] - 1.5 <= design.height_m
              <= entry.height_m_range[1] + 1.5,
              f"{round(design.height_m, 1)} m against catalogue {entry.height_m_range}")
    return {"design_id": design.id, "type": design.type,
            "state": "pass" if all(r["state"] == "pass" for r in results) else "fail", "checks": results}
