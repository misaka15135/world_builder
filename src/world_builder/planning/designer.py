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
    storeys: tuple[int, int]
    storey_height_m: float
    roof: str
    roof_height_m: float
    setback_m: float
    stair: str
    room_uses: tuple[tuple[str, ...], ...]
    aspect: float


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
        if chosen >= fewest and squeezed >= 2.6:
            storey_height = round(squeezed, 3)
        else:
            while chosen > 1 and chosen * storey_height + template.roof_height_m > site.max_height_m:
                chosen -= 1
            squeezed = (site.max_height_m - template.roof_height_m) / chosen
            storey_height = round(max(2.6, min(storey_height, squeezed)), 3)
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
        run = 8.0 if width >= 14 else 4.0
        ground = storeys_out[0]
        stair = {"representation": "straight_stair", "side": "east",
                 "x0": round(ground.x1 - stair_void, 3), "y0": round(ground.y0 + 3.0, 3),
                 "width_m": 2.0, "run_m": run, "rise_m": storey_height, "steps": 20,
                 "landing_m": 2.0, "void": [round(ground.x1 - stair_void, 3),
                                            round(ground.x1 - stair_void + 3.0, 3),
                                            round(ground.y0 + 3.0, 3), round(ground.y0 + 3.0 + run + 2.0, 3)]}
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
                           entry_side=entry_side, entry_offset_m=2.0, entry_width_m=2.0,
                           entry_height_m=2.4, stair=stair, furniture=tuple(furniture),
                           materials=dict(pack.materials), height_m=round(height, 3))


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
