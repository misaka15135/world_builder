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
from dataclasses import dataclass, replace
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
# A two-room plan puts a stair well (3 m) plus a wall either side of it across
# the short span, and each room needs a metre of depth either side of the
# middle partition. Below these the plan has no room in it, and the design has
# to say so instead of emitting a building whose rooms have negative width —
# which is what a 1x1 m plot used to produce (measured 2026-09-28).
MIN_PLAN_WIDTH_M = 6.0
MIN_PLAN_DEPTH_M = 5.0
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
    # `kind: "compound"` (work order 017 class 3): a castle is several volumes —
    # a keep, corner towers, a hall and a curtain wall — not one box.
    compound: tuple[tuple[str, float, str], ...] = ()
    # How many interior compartments a compound part needs. Only the keep has
    # any today: a tower is a solid landmark and a great hall is one tall room.
    compound_storeys: tuple[tuple[str, int], ...] = ()
    # A compound part is a box unless it says otherwise; a curtain-wall tower is
    # round, which the target can now step into a polygon (work order 017).
    compound_shapes: tuple[tuple[str, str], ...] = ()
    # `kind: "cylinders"` (work order 017 class 3): a tank farm — one or more
    # round vessels on one plot. The first geometry the adapter has that is not
    # a box; the target steps the circle so it survives at block scale.
    vessel_diameter_m: float | None = None
    vessel_height_m: float | None = None
    vessel_count: int | None = None
    vessel_roof: str | None = None
    # `kind: "dock"` (work order 017 class 3): a basin cut below the quay with a
    # gate on the water side and a gantry over it — the last harbour type.
    basin_depth_m: float | None = None
    basin_margin_m: float | None = None
    # Curtain-wall layout: a rectangle of runs, or a polygonal ring for the
    # "circular wall around the castle" the brief asks for.
    ring: str = "rectangle"


OPEN_SPACE_PAVING = ("stone", "path", "gravel")
# `crate` and `stack` are the yard vocabulary: a freight yard stacks pallets, a
# container yard stacks boxes, and both are surface plans rather than buildings.
OPEN_SPACE_FIXTURES = ("lamp", "bench", "tree", "planter", "crate", "stack")
# Compound volumes: role, height in metres, roof style. The layout rule derives
# footprints from the site, so a template only states how tall each part is.
# `gate` is the gatehouse over the curtain-wall opening (work order 017 main
# line): two piers beside the gap and a lintel above it. `ramp` is not a
# template part at all — the layout rule emits it as the stepped approach onto
# the raised gate platform, which is why it is accepted but never declared.
COMPOUND_ROLES = ("wall", "tower", "keep", "hall", "gate")
COMPOUND_RAMP_ROLES = ("ramp",)
COMPOUND_RINGS = ("rectangle", "circle")
# Class 3 vocabulary (work order 017): until now every volume was an
# axis-aligned box, so a silo had to be drawn as one. A cylinder design states
# how many vessels stand on the plot, how fat and how tall each is, and how it
# is capped; the target steps the circle into a ring of boxes.
CYLINDER_ROOFS = ("flat", "dome")
CYLINDER_MIN_RADIUS_M = 2.0
CYLINDER_GAP_M = 2.0
# A compound part is a box unless it says otherwise: a curtain-wall tower is
# round, and the target steps that into a polygon the same way it steps a silo.
COMPOUND_SHAPES = ("box", "round")
# A gate platform sits above the bailey floor, so its approach treads step
# outward past the site edge and onto the street that the gate faces. The
# validator allows exactly that, and only on the entry side.
GATE_PLATFORM_M = 0.75
GATE_TREAD_M = 0.8
RAMP_EXCURSION_M = 4.0
GATE_OPENING_H_M = 4.0


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


@dataclass(frozen=True)
class DockDesign:
    """A dry dock: an excavated basin, a gate and a gantry over it.

    Class 3 geometry (work order 017 main line) and the last type the harbour
    was missing. The basin is cut *below* the quay: the target places an air
    volume to excavate it, which is the one place this pipeline removes material
    rather than adding it. The gantry is the silhouette the catalogue asks for
    (`basin_with_gantry`), and the gate sits on the face that looks at the water.
    """

    id: str
    type: str
    role: str
    design_state: str
    site_id: str
    x0: float
    y0: float
    x1: float
    y1: float
    depth_m: float
    gate_side: str
    gantry_height_m: float
    materials: dict

    @property
    def area_m2(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)

    @property
    def height_m(self) -> float:
        """What stands above grade: the gantry, which is the reading silhouette."""
        return self.gantry_height_m

    def to_dict(self) -> dict:
        return {"design_version": DESIGN_VERSION, "id": self.id, "type": self.type,
                "role": self.role, "design_state": self.design_state, "site_id": self.site_id,
                "kind": "dock",
                "outline": [round(self.x0, 3), round(self.y0, 3), round(self.x1, 3), round(self.y1, 3)],
                "depth_m": round(self.depth_m, 3), "gate_side": self.gate_side,
                "gantry_height_m": round(self.gantry_height_m, 3),
                "materials": dict(self.materials)}


@dataclass(frozen=True)
class CylinderDesign:
    """A tank farm: one or more cylindrical vessels on one plot.

    Class 3 geometry (work order 017 main line). Every other plan this module
    produces is made of axis-aligned boxes; a silo or a storage tank is round,
    so the design states each vessel as a centre, a radius, a height and a cap
    and leaves the stepping to the target — a ring of chord boxes per metre,
    which is the closest a 1 m voxel grid comes to a circle. The vessels stand
    in a grid with a service gap, and any that would leave the plot are dropped
    rather than pushed through a neighbour.
    """

    id: str
    type: str
    role: str
    design_state: str
    site_id: str
    x0: float
    y0: float
    x1: float
    y1: float
    barrels: tuple[dict, ...]
    height_m: float
    materials: dict

    @property
    def area_m2(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)

    def to_dict(self) -> dict:
        return {"design_version": DESIGN_VERSION, "id": self.id, "type": self.type,
                "role": self.role, "design_state": self.design_state, "site_id": self.site_id,
                "kind": "cylinders",
                "outline": [round(self.x0, 3), round(self.y0, 3), round(self.x1, 3), round(self.y1, 3)],
                "height_m": round(self.height_m, 3),
                "barrels": [dict(item) for item in self.barrels],
                "materials": dict(self.materials)}


@dataclass(frozen=True)
class CompoundDesign:
    """Several volumes on one site: a castle's keep, towers, hall and wall.

    Each volume is a hollow shell with a roof, stated in absolute scene
    coordinates so the assembler can emit it without re-deriving the layout.
    Interiors and gates beyond the curtain wall's opening are not part of this
    kind yet — the work order records that rather than implying them.
    """

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
    volumes: tuple[dict, ...]
    height_m: float
    materials: dict

    @property
    def area_m2(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)

    def to_dict(self) -> dict:
        return {"design_version": DESIGN_VERSION, "id": self.id, "type": self.type,
                "role": self.role, "design_state": self.design_state, "site_id": self.site_id,
                "kind": "compound",
                "outline": [round(self.x0, 3), round(self.y0, 3), round(self.x1, 3), round(self.y1, 3)],
                "height_m": round(self.height_m, 3),
                "volumes": [dict(item) for item in self.volumes],
                "materials": dict(self.materials)}


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
        if isinstance(raw, dict) and raw.get("kind") == "compound":
            if set(raw) not in ({"kind", "parts"}, {"kind", "parts", "ring"}):
                raise SceneError(code, f"{type_name} must contain kind, parts and an optional ring")
            ring = raw.get("ring", "rectangle")
            if ring not in COMPOUND_RINGS:
                raise SceneError(code, f"{type_name}.ring must be one of {', '.join(COMPOUND_RINGS)}")
            parts = raw["parts"]
            if not isinstance(parts, list) or not parts:
                raise SceneError(code, f"{type_name}.parts must list the volumes")
            declared = []
            interior = []
            shapes = []
            for item in parts:
                if not isinstance(item, dict) or set(item) not in (
                        {"role", "height_m", "roof"}, {"role", "height_m", "roof", "storeys"},
                        {"role", "height_m", "roof", "shape"},
                        {"role", "height_m", "roof", "storeys", "shape"}):
                    raise SceneError(code, f"{type_name}.parts entries need role, height_m, roof "
                                           f"and optional storeys and shape")
                if item["role"] not in COMPOUND_ROLES or item["roof"] not in ROOF_STYLES:
                    raise SceneError(code, f"{type_name}: unknown role {item['role']!r} "
                                           f"or roof {item['roof']!r}")
                if not 3.0 <= float(item["height_m"]) <= 90.0:
                    raise SceneError(code, f"{type_name}.{item['role']}.height_m must be 3—90 m")
                count = item.get("storeys", 1)
                if type(count) is not int or not 1 <= count <= 6:
                    raise SceneError(code, f"{type_name}.{item['role']}.storeys must be 1—6")
                shape = item.get("shape", "box")
                if shape not in COMPOUND_SHAPES:
                    raise SceneError(code, f"{type_name}.{item['role']}.shape must be one of "
                                           f"{', '.join(COMPOUND_SHAPES)}")
                declared.append((item["role"], float(item["height_m"]), item["roof"]))
                interior.append((item["role"], count))
                shapes.append((item["role"], shape))
            parsed[type_name] = DesignTemplate(type=type_name, kind="compound",
                                               compound=tuple(declared),
                                               compound_storeys=tuple(interior),
                                               compound_shapes=tuple(shapes), ring=ring)
            continue
        if isinstance(raw, dict) and raw.get("kind") == "cylinders":
            keys = {"kind", "diameter_m", "height_m", "count", "roof"}
            if set(raw) != keys:
                raise SceneError(code, f"{type_name} must contain exactly {', '.join(sorted(keys))}")
            if not 4.0 <= float(raw["diameter_m"]) <= 60.0:
                raise SceneError(code, f"{type_name}.diameter_m must be 4—60 m")
            if not 3.0 <= float(raw["height_m"]) <= 40.0:
                raise SceneError(code, f"{type_name}.height_m must be 3—40 m")
            if type(raw["count"]) is not int or not 1 <= raw["count"] <= 12:
                raise SceneError(code, f"{type_name}.count must be 1—12 vessels")
            if raw["roof"] not in CYLINDER_ROOFS:
                raise SceneError(code, f"{type_name}.roof must be one of {', '.join(CYLINDER_ROOFS)}")
            parsed[type_name] = DesignTemplate(type=type_name, kind="cylinders",
                                               vessel_diameter_m=float(raw["diameter_m"]),
                                               vessel_height_m=float(raw["height_m"]),
                                               vessel_count=raw["count"], vessel_roof=raw["roof"])
            continue
        if isinstance(raw, dict) and raw.get("kind") == "dock":
            keys = {"kind", "depth_m", "margin_m"}
            if set(raw) != keys:
                raise SceneError(code, f"{type_name} must contain exactly {', '.join(sorted(keys))}")
            if not 2.0 <= float(raw["depth_m"]) <= 12.0:
                raise SceneError(code, f"{type_name}.depth_m must be 2—12 m")
            if not 2.0 <= float(raw["margin_m"]):
                raise SceneError(code, f"{type_name}.margin_m must be at least 2 m")
            parsed[type_name] = DesignTemplate(type=type_name, kind="dock",
                                               basin_depth_m=float(raw["depth_m"]),
                                               basin_margin_m=float(raw["margin_m"]))
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


def _insets(width: float, depth: float, storeys: int, setback_m: float,
            fingerprint: str = "") -> list[tuple[float, float, float, float]]:
    """Per-storey insets (west, east, south, north), ground storey flush.

    Building-skill rule 1: a building has to read as more than one volume, so
    the massing steps. The east side stays put because the stair strip runs
    along it; the other sides step back by whole metres, capped so the rooms keep
    their floor space. Which side steps first — and whether the top two storeys
    step instead of only the top one — comes from the building's own
    fingerprint, so a street of identical plots does not become a row of
    identical boxes. Two-storey buildings step only on generous plots.
    """
    insets = [(0.0, 0.0, 0.0, 0.0) for _ in range(storeys)]
    if storeys < 2 or setback_m <= 0:
        return insets
    cap = min(setback_m, width - 9.0, depth / 2 - 3.0)
    step = math.floor(max(0.0, cap))
    if step < 1:
        return insets
    if storeys == 2 and min(width, depth) < 14.0:
        return insets
    digest = int.from_bytes(hashlib.sha256(fingerprint.encode("utf-8")).digest()[:4], "big")
    faces = ("west", "south", "north")
    first = faces[digest % len(faces)]
    levels = {storeys - 1}
    if storeys >= 3 and (digest >> 3) % 3 == 0:
        levels.add(storeys - 2)
    for level in levels:
        insets[level] = (float(step) if first == "west" else 0.0, 0.0,
                         float(step) if first == "south" else 0.0,
                         float(step) if first == "north" else 0.0)
    return insets


def design_building(site: Site, entry, pack: SettingPack, template: DesignTemplate, *,
                    entry_side: str = "east", seed: int = 1,
                    storeys: int | None = None) -> BuildingDesign:
    """Design one building inside the site's envelope."""
    if entry_side not in ENTRY_SIDES:
        raise SceneError("design.entry_side", f"unknown entry side {entry_side!r}")
    width_span = site.x1 - site.x0
    depth_span = site.y1 - site.y0
    # An envelope that cannot hold the plan is refused here rather than fitted:
    # a building whose rooms have negative width is not a design, it is a bug
    # the scoped failure feedback should have caught (work order 018).
    if width_span < MIN_PLAN_WIDTH_M - 1e-6 or depth_span < MIN_PLAN_DEPTH_M - 1e-6:
        raise SceneError("design.envelope",
                         f"{site.id}: a {round(width_span, 1)}x{round(depth_span, 1)} m plot cannot hold a "
                         f"stair well and two rooms; {MIN_PLAN_WIDTH_M}x{MIN_PLAN_DEPTH_M} m is the floor")
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
    if spans[entry_side] < DOOR_SPAN_MIN_M - 1e-6:
        raise SceneError("design.envelope",
                         f"{site.id}: no face is long enough for a {ENTRY_DOOR_M} m door "
                         f"({round(spans[entry_side], 2)} m at best, {DOOR_SPAN_MIN_M} m needed)")
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
    # The envelope is hard: a plot too flat for the minimum storey and its roof
    # has no design, and saying so is what lets one plot fail alone (018).
    if height > site.max_height_m + 1e-6:
        raise SceneError("design.envelope",
                         f"{site.id}: {round(height, 2)} m of storey and roof does not fit the "
                         f"{round(site.max_height_m, 2)} m envelope")
    insets = _insets(width, depth, chosen, template.setback_m, fingerprint=site.id)
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
                      fixture_cap: int = 32) -> OpenSpaceDesign:
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


def design_dock(site: Site, pack: SettingPack, template: DesignTemplate, *,
                entry_side: str = "south") -> DockDesign:
    """Cut a dry dock into its plot (work order 017 class 3).

    The basin is the plot minus a margin for the quay edge, its floor is the
    template's depth below grade, and the gate goes on the face that looks at
    the water — that is the side the vessel enters from, so it is read from the
    site's own `water` need rather than assumed. A plot too small for a basin
    with working room around it is refused, which lets the scoped failure
    feedback drop this one plot (018) instead of cutting a trench through the
    quay.
    """
    if template.kind != "dock" or not template.basin_depth_m:
        raise SceneError("design.kind", f"{template.type} is not a dock template")
    if entry_side not in ENTRY_SIDES:
        raise SceneError("design.entry_side", f"unknown entry side {entry_side!r}")
    margin = float(template.basin_margin_m or 3.0)
    width, depth = site.x1 - site.x0, site.y1 - site.y0
    if width < 2 * margin + MIN_PLAN_WIDTH_M or depth < 2 * margin + MIN_PLAN_WIDTH_M:
        raise SceneError("design.envelope",
                         f"{site.id}: a {round(width, 1)}x{round(depth, 1)} m plot cannot hold a basin "
                         f"with a {margin} m working margin")
    basin_depth = min(float(template.basin_depth_m), float(site.max_height_m))
    return DockDesign(id=f"design_{site.id}", type=template.type, role=site.role,
                      design_state=site.design_state, site_id=site.id,
                      x0=round(site.x0 + margin, 3), y0=round(site.y0 + margin, 3),
                      x1=round(site.x1 - margin, 3), y1=round(site.y1 - margin, 3),
                      depth_m=round(basin_depth, 3), gate_side=entry_side,
                      # The crane has to clear the vessel and the catalogue's
                      # height band; it is stated as a height, not a shape.
                      gantry_height_m=round(max(6.0, min(site.max_height_m, basin_depth + 8.0)), 3),
                      materials=dict(pack.materials))


def validate_dock(design: DockDesign, site: Site) -> dict:
    """Independent checks on a dry dock: inside the plot and deep enough to float a hull."""
    results: list[dict] = []

    def check(rule: str, passed: bool, message: str) -> None:
        results.append({"rule": rule, "state": "pass" if passed else "fail", "message": message})

    check("design.outline", site.x0 - 2e-3 <= design.x0 and design.x1 <= site.x1 + 2e-3
          and site.y0 - 2e-3 <= design.y0 and design.y1 <= site.y1 + 2e-3,
          f"basin {round(design.area_m2)} m² inside the plot")
    check("design.basin_room",
          design.x1 - design.x0 >= MIN_PLAN_WIDTH_M and design.y1 - design.y0 >= MIN_PLAN_WIDTH_M,
          f"basin {round(design.x1 - design.x0, 1)}x{round(design.y1 - design.y0, 1)} m takes a hull")
    check("design.basin_depth", 2.0 - 2e-3 <= design.depth_m <= site.max_height_m + 2e-3,
          f"{design.depth_m} m of basin against the {site.max_height_m} m envelope")
    check("design.gate_side", design.gate_side in ENTRY_SIDES,
          f"gate on the {design.gate_side} face")
    return {"design_id": design.id, "type": design.type, "kind": "dock",
            "state": "pass" if all(item["state"] == "pass" for item in results) else "fail",
            "checks": results}


def _shrink_site(site: Site, fraction: float) -> Site:
    """The same plot, pulled in from every edge by a fraction of its short side."""
    if fraction <= 0.0:
        return site
    inset = min(site.x1 - site.x0, site.y1 - site.y0) * fraction / 2
    return replace(site, x0=site.x0 + inset, y0=site.y0 + inset,
                   x1=site.x1 - inset, y1=site.y1 - inset)


def design_sites(siting, pack: SettingPack, templates: dict, *, seed: int = 1,
                 shrink_steps: tuple[float, ...] = (0.0, 0.10, 0.20)) -> tuple[list, list[dict], set[str]]:
    """Design every sited plot, keeping one plot's failure to that plot.

    Work order 018: a single building that cannot be designed must cost that
    building and nothing else. The rule is a scoped retry — first on the plot as
    sited, then on the same plot pulled in from its edges, which is the "re-fit
    the envelope" step that stays inside one plot. Only when every attempt fails
    is the plot dropped, and it is dropped **with its reason recorded** rather
    than by relaxing the brief: the rest of the city assembles unchanged, and
    the caller can report exactly which plots are missing and why.

    Returns the designs, one failure record per dropped plot, and the set of
    types that have no template at all.
    """
    designs: list = []
    failures: list[dict] = []
    skipped: set[str] = set()
    for site in siting.sites:
        template = templates.get(site.type)
        if template is None:
            skipped.add(site.type)
            continue
        block = siting.block(site.block_id)
        entry_side = "south" if abs(block.centre[1] - site.y0) < abs(block.centre[1] - site.y1) else "north"
        attempt_record = None
        for attempt, shrink in enumerate(shrink_steps, start=1):
            try:
                designs.append(design(_shrink_site(site, shrink), pack.entry(site.type), pack, template,
                                      entry_side=entry_side, seed=seed))
                break
            except SceneError as error:
                attempt_record = {"site_id": site.id, "type": site.type, "code": error.code,
                                  "message": str(error), "attempts": attempt, "shrink": shrink}
        else:
            failures.append(attempt_record)
    return designs, failures, skipped


def design(site: Site, entry, pack: SettingPack, template: DesignTemplate, *,
           entry_side: str = "east", seed: int = 1):
    """Stage E entry point: a building design or a ground plan, by template kind."""
    if template.kind == "open_space":
        return design_open_space(site, template, entry_side=entry_side)
    if template.kind == "compound":
        return design_compound(site, pack, template, entry_side=entry_side)
    if template.kind == "cylinders":
        return design_cylinders(site, pack, template)
    if template.kind == "dock":
        return design_dock(site, pack, template, entry_side=entry_side)
    return design_building(site, entry, pack, template, entry_side=entry_side, seed=seed)


def _overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return min(a[2], b[2]) - max(a[0], b[0]) > 1e-6 and min(a[3], b[3]) - max(a[1], b[1]) > 1e-6


def _compound_side_span(rect: tuple[float, float, float, float], side: str) -> float:
    return (rect[2] - rect[0]) if side in {"north", "south"} else (rect[3] - rect[1])


def design_cylinders(site: Site, pack: SettingPack, template: DesignTemplate) -> CylinderDesign:
    """A bank of round vessels on one plot (work order 017 class 3).

    The template states one vessel; the rule decides how many of them fit. They
    are laid in a grid with a service gap, centred on the plot, and the radius
    shrinks until the grid fits rather than the vessels overlapping. Anything
    that still would not fit is dropped: a tank farm with three tanks is honest,
    a tank farm with three tanks inside each other is not.
    """
    if template.kind != "cylinders" or not template.vessel_diameter_m:
        raise SceneError("design.kind", f"{template.type} is not a cylinder template")
    width, depth = site.x1 - site.x0, site.y1 - site.y0
    count = int(template.vessel_count or 1)
    margin = 1.0
    wanted = float(template.vessel_diameter_m) / 2

    def grid_for(number: int) -> tuple[int, int, float]:
        columns = max(1, math.ceil(math.sqrt(number)))
        rows = max(1, math.ceil(number / columns))
        cell = min((width - 2 * margin) / columns, (depth - 2 * margin) / rows)
        return columns, rows, min(wanted, (cell - CYLINDER_GAP_M) / 2)

    # A narrow plot can hold the requested number of vessels only by shrinking
    # them into pipes. Fewer, fatter vessels are the honest reading: the rule
    # steps the count down while the radius stays under 60 % of the template's.
    chosen = 1
    for number in range(count, 0, -1):
        _, _, candidate = grid_for(number)
        if candidate >= 0.6 * wanted:
            chosen = number
            break
    columns, rows, radius = grid_for(chosen)
    height = min(float(template.vessel_height_m or 10.0), float(site.max_height_m))
    barrels: list[dict] = []
    if radius >= CYLINDER_MIN_RADIUS_M:
        step_x = (width - 2 * margin) / columns
        step_y = (depth - 2 * margin) / rows
        for index in range(chosen):
            column, row = index % columns, index // columns
            centre = (site.x0 + margin + step_x * (column + 0.5),
                      site.y0 + margin + step_y * (row + 0.5))
            if (site.x0 + radius - 2e-3 <= centre[0] <= site.x1 - radius + 2e-3
                    and site.y0 + radius - 2e-3 <= centre[1] <= site.y1 - radius + 2e-3):
                barrels.append({"id": f"vessel{index}", "cx": round(centre[0], 3),
                                "cy": round(centre[1], 3), "radius_m": round(radius, 3),
                                "height_m": round(height, 3), "roof": template.vessel_roof})
    if not barrels:
        raise SceneError("design.no_fit",
                         f"{template.type} needs {CYLINDER_MIN_RADIUS_M} m of radius; "
                         f"the plot is {round(width, 1)}x{round(depth, 1)} m")
    used_x = [barrel["cx"] - barrel["radius_m"] for barrel in barrels] + \
             [barrel["cx"] + barrel["radius_m"] for barrel in barrels]
    used_y = [barrel["cy"] - barrel["radius_m"] for barrel in barrels] + \
             [barrel["cy"] + barrel["radius_m"] for barrel in barrels]
    return CylinderDesign(id=f"design_{site.id}", type=template.type, role=site.role,
                          design_state=site.design_state, site_id=site.id,
                          x0=round(min(used_x), 3), y0=round(min(used_y), 3),
                          x1=round(max(used_x), 3), y1=round(max(used_y), 3),
                          barrels=tuple(barrels), height_m=round(height, 3),
                          materials=dict(pack.materials))


def validate_cylinder(design: CylinderDesign, site: Site) -> dict:
    """Independent checks on a tank farm: inside the plot, clear of each other."""
    results: list[dict] = []

    def check(rule: str, passed: bool, message: str) -> None:
        results.append({"rule": rule, "state": "pass" if passed else "fail", "message": message})

    check("design.outline", site.x0 - 2e-3 <= design.x0 and design.x1 <= site.x1 + 2e-3
          and site.y0 - 2e-3 <= design.y0 and design.y1 <= site.y1 + 2e-3,
          f"vessel bank {round(design.area_m2)} m² inside the plot")
    check("design.height", design.height_m <= site.max_height_m + 2e-3,
          f"{design.height_m} m against the envelope {site.max_height_m} m")
    check("design.vessels_inside",
          all(site.x0 - 2e-3 <= barrel["cx"] - barrel["radius_m"]
              and barrel["cx"] + barrel["radius_m"] <= site.x1 + 2e-3
              and site.y0 - 2e-3 <= barrel["cy"] - barrel["radius_m"]
              and barrel["cy"] + barrel["radius_m"] <= site.y1 + 2e-3
              for barrel in design.barrels),
          f"{len(design.barrels)} vessel(s) inside the plot")
    clear = all(math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"]) >= a["radius_m"] + b["radius_m"] - 2e-3
                for index, a in enumerate(design.barrels)
                for b in design.barrels[index + 1:])
    check("design.vessels_clear", clear, "no two vessels touch")
    check("design.vessel_size",
          all(barrel["radius_m"] >= CYLINDER_MIN_RADIUS_M for barrel in design.barrels),
          f"every vessel is at least {CYLINDER_MIN_RADIUS_M} m in radius")
    return {"design_id": design.id, "type": design.type, "kind": "cylinders",
            "state": "pass" if all(item["state"] == "pass" for item in results) else "fail",
            "checks": results}


def _compound_interior(rect: tuple[float, float, float, float], height_m: float,
                       compartments: int) -> tuple[list[float], dict | None]:
    """Floor levels and a corner stair for one compound volume (017 main line).

    A keep is the one part of a castle with rooms above the ground: its height
    is split into compartments no taller than the storey range the rest of the
    pipeline uses, and one straight flight runs up a side so every level can be
    reached. A great hall is a single tall room and a tower is a landmark, so
    both stay one space — this returns nothing for them.
    """
    count = max(1, min(int(compartments), max(1, int(math.floor(height_m / 3.2)))))
    if count < 2:
        return [], None
    levels = [round(height_m * index / count, 3) for index in range(1, count)]
    span_x, span_y = rect[2] - rect[0], rect[3] - rect[1]
    run = max(2.0, min(span_x, span_y) - 1.6)
    if span_x >= span_y:
        stair = {"x0": round(rect[0] + 0.6, 3), "y0": round(rect[1] + 0.6, 3),
                 "x1": round(rect[0] + 0.6 + run, 3), "y1": round(rect[1] + 1.7, 3),
                 "run": "x"}
    else:
        stair = {"x0": round(rect[0] + 0.6, 3), "y0": round(rect[1] + 0.6, 3),
                 "x1": round(rect[0] + 1.7, 3), "y1": round(rect[1] + 0.6 + run, 3),
                 "run": "y"}
    return levels, stair


def design_compound(site: Site, pack: SettingPack, template: DesignTemplate, *,
                    entry_side: str = "south") -> CompoundDesign:
    """Lay a castle on its site: curtain wall with a gate, towers, keep, hall.

    The template states how tall each part is; the layout rule derives the
    footprints from the site, so a larger bailey gets a larger keep rather than
    the same box scaled. Parts that do not fit are dropped instead of being
    forced through each other, and every part is capped by the site envelope.
    """
    if entry_side not in ENTRY_SIDES:
        raise SceneError("design.entry_side", f"unknown entry side {entry_side!r}")
    if template.kind != "compound" or not template.compound:
        raise SceneError("design.kind", f"{template.type} is not a compound template")
    declared = {role: (height, roof) for role, height, roof in template.compound}
    compartments = {role: count for role, count in template.compound_storeys}
    shapes = {role: shape for role, shape in template.compound_shapes}
    ceiling = float(site.max_height_m)
    # The template states absolute heights; when the envelope cannot hold the
    # tallest part, every part is scaled by the same factor so the castle keeps
    # its silhouette (a flat-topped castle with four towers and a keep all at
    # the envelope is not a castle). 3 m stays the floor for any part.
    tallest = max(height for height, _ in declared.values())
    scale = min(1.0, ceiling / tallest) if tallest > 0 else 1.0

    def part(role: str, rect: tuple[float, float, float, float], fallback: float = 10.0, *,
             base_m: float = 0.0, top_m: float | None = None, roof: str | None = None) -> dict:
        height, declared_roof = declared.get(role, (fallback, "flat"))
        if top_m is None:
            top = max(base_m + 3.0, min(height * scale, ceiling))
        else:
            # Ramps and lintels state their own top: a gate platform is not a
            # scaled version of a curtain wall, and a lintel starts in mid-air.
            top = min(top_m, ceiling)
        return {"id": f"{site.id}_{role}{len(volumes)}", "role": role,
                "x0": round(rect[0], 3), "y0": round(rect[1], 3),
                "x1": round(rect[2], 3), "y1": round(rect[3], 3),
                "base_m": round(base_m, 3), "height_m": round(top, 3),
                "shape": shapes.get(role, "box"),
                "roof": declared_roof if roof is None else roof}

    x0, y0, x1, y1 = site.x0, site.y0, site.x1, site.y1
    width, depth = x1 - x0, y1 - y0
    wall = 1.0
    gate = max(3.0, min(4.0, (width if entry_side in {"north", "south"} else depth) * 0.2))
    volumes: list[dict] = []
    # Curtain wall: four runs, with the street side split around its gate.
    runs = [("south", (x0, y0, x1, y0 + wall)),
            ("north", (x0, y1 - wall, x1, y1)),
            ("west", (x0, y0 + wall, x0 + wall, y1 - wall)),
            ("east", (x1 - wall, y0 + wall, x1, y1 - wall))]
    ring_circle = template.ring == "circle" and min(width, depth) >= 30.0
    centre = ((x0 + x1) / 2, (y0 + y1) / 2)
    radius = min(width, depth) / 2 - 1.5
    if ring_circle:
        # "圆形环绕的城墙": the wall follows a polygonal ring whose chords are
        # short boxes, so the bailey reads as a round courtyard. The street side
        # keeps its gate: the segments inside the approach arc are skipped.
        segments = max(16, min(32, int(math.pi * radius / 2.0)))
        approach = {"south": -math.pi / 2, "north": math.pi / 2,
                    "west": math.pi, "east": 0.0}[entry_side]
        for index in range(segments):
            angle = 2 * math.pi * index / segments
            midpoint = angle + math.pi / segments
            gap = abs((midpoint - approach + math.pi) % (2 * math.pi) - math.pi)
            if gap * radius <= gate / 2:
                continue
            ax, ay = centre[0] + radius * math.cos(angle), centre[1] + radius * math.sin(angle)
            bx, by = (centre[0] + radius * math.cos(angle + 2 * math.pi / segments),
                      centre[1] + radius * math.sin(angle + 2 * math.pi / segments))
            volumes.append(part("wall", (min(ax, bx) - wall / 2, min(ay, by) - wall / 2,
                                         max(ax, bx) + wall / 2, max(ay, by) + wall / 2)))
    else:
        for name, rect in runs:
            if name != entry_side:
                volumes.append(part("wall", rect))
                continue
            if name in {"north", "south"}:
                centre = (x0 + x1) / 2
                volumes.append(part("wall", (rect[0], rect[1], centre - gate / 2, rect[3])))
                volumes.append(part("wall", (centre + gate / 2, rect[1], rect[2], rect[3])))
            else:
                centre = (y0 + y1) / 2
                volumes.append(part("wall", (rect[0], rect[1], rect[2], centre - gate / 2)))
                volumes.append(part("wall", (rect[0], centre + gate / 2, rect[2], rect[3])))
    # Corner towers, then the keep, then the hall along the far side from the gate.
    tower = max(6.0, min(10.0, min(width, depth) * 0.18))
    # 门楼 (work order 017 main line): the opening in the curtain wall gets a
    # gatehouse — two piers either side of the gap and a lintel spanning it — so
    # the gate reads as a building rather than a hole in a wall. Its threshold
    # sits on a stone platform reached by stepped ramps on both sides, which is
    # what a gate does when the ground outside lies below the bailey floor.
    mid_x, mid_y = (x0 + x1) / 2, (y0 + y1) / 2
    if "gate" in declared and declared["gate"][0] * scale - GATE_OPENING_H_M >= 1.0:
        along_x = entry_side in {"north", "south"}
        if ring_circle:
            approach = {"south": -math.pi / 2, "north": math.pi / 2,
                        "west": math.pi, "east": 0.0}[entry_side]
            gx = mid_x + radius * math.cos(approach)
            gy = mid_y + radius * math.sin(approach)
            outward = {"south": -1.0, "north": 1.0, "west": -1.0, "east": 1.0}[entry_side]
        else:
            outside_x = x0 + wall / 2 if entry_side == "west" else x1 - wall / 2
            outside_y = y0 + wall / 2 if entry_side == "south" else y1 - wall / 2
            gx = mid_x if along_x else outside_x
            gy = outside_y if along_x else mid_y
            outward = {"south": -1.0, "north": 1.0, "west": -1.0, "east": 1.0}[entry_side]
        band = wall
        pier = max(1.2, min(2.5, min(width, depth) * 0.05))
        gate_top = declared["gate"][0] * scale
        if along_x:
            throat = (gx - gate / 2, gy - band / 2, gx + gate / 2, gy + band / 2)
            piers = [(gx - gate / 2 - pier, gy - band / 2, gx - gate / 2, gy + band / 2),
                     (gx + gate / 2, gy - band / 2, gx + gate / 2 + pier, gy + band / 2)]
        else:
            throat = (gx - band / 2, gy - gate / 2, gx + band / 2, gy + gate / 2)
            piers = [(gx - band / 2, gy - gate / 2 - pier, gx + band / 2, gy - gate / 2),
                     (gx - band / 2, gy + gate / 2, gx + band / 2, gy + gate / 2 + pier)]
        for rect in piers:
            volumes.append(part("gate", rect, 14.0))
        volumes.append(part("gate", throat, 14.0, base_m=GATE_OPENING_H_M, top_m=gate_top))
        volumes.append(part("ramp", throat, top_m=GATE_PLATFORM_M))
        for index in (1, 2):
            tread_top = round(GATE_PLATFORM_M - index * GATE_PLATFORM_M / 3.0, 3)
            for sign in (outward, -outward):
                if along_x:
                    near = gy - band / 2 if sign < 0 else gy + band / 2
                    rect = (gx - gate / 2, near + sign * (index - 1) * GATE_TREAD_M,
                            gx + gate / 2, near + sign * index * GATE_TREAD_M)
                else:
                    near = gx - band / 2 if sign < 0 else gx + band / 2
                    rect = (near + sign * (index - 1) * GATE_TREAD_M, gy - gate / 2,
                            near + sign * index * GATE_TREAD_M, gy + gate / 2)
                volumes.append(part("ramp", (min(rect[0], rect[2]), min(rect[1], rect[3]),
                                              max(rect[0], rect[2]), max(rect[1], rect[3])),
                                    top_m=tread_top))
    # Towers sit inside the curtain wall, so they touch its inner face rather
    # than overlapping the runs at the corners.
    if ring_circle:
        # Towers ride the ring at the four diagonal points, just inside it.
        cx0, cy0 = centre
        # Towers straddle the ring itself: their mass is part of the curtain, so
        # they neither overlap the wall run (allowed) nor reach into the bailey
        # where the keep stands.
        centres = [(cx0 + radius * math.cos(math.pi / 4 + step * math.pi / 2) - tower / 2,
                    cy0 + radius * math.sin(math.pi / 4 + step * math.pi / 2) - tower / 2)
                   for step in range(4)]
    else:
        centres = [(x0 + wall, y0 + wall), (x1 - wall - tower, y0 + wall),
                   (x0 + wall, y1 - wall - tower), (x1 - wall - tower, y1 - wall - tower)]
    for cx, cy in centres:
        rect = (cx, cy, cx + tower, cy + tower)
        if not any(_overlaps(rect, (v["x0"], v["y0"], v["x1"], v["y1"])) for v in volumes
                   if v["role"] == "keep"):
            volumes.append(part("tower", rect, 18.0))
    # The keep has to clear the towers on every side, so its side shrinks with
    # them instead of assuming a roomy bailey.
    keep_side = max(6.0, min(min(width, depth) * 0.42, min(width, depth) - 2 * (wall + tower + 1.5)))
    keep = ((x0 + x1) / 2 - keep_side / 2, (y0 + y1) / 2 - keep_side / 2,
            (x0 + x1) / 2 + keep_side / 2, (y0 + y1) / 2 + keep_side / 2)
    keep_volume = part("keep", keep, 16.0)
    # 城堡室内 (work order 017 main line): the keep is the one part with floors
    # inside. A straight flight up one side connects every level, so the rooms
    # above the ground can actually be reached, and the face towards the gate
    # keeps a doorway.
    keep_levels, keep_stair = _compound_interior(keep, keep_volume["height_m"],
                                                compartments.get("keep", 3))
    if keep_levels:
        keep_volume["levels_m"] = keep_levels
    if keep_stair is not None:
        keep_volume["stair"] = keep_stair
    keep_volume["door"] = {"side": entry_side,
                           "width_m": round(min(2.2, _compound_side_span(keep, entry_side) * 0.4), 3),
                           "height_m": 3.0}
    volumes.append(keep_volume)
    hall_depth = max(6.0, depth * 0.22)
    hall_width = max(8.0, width * 0.5)
    if ring_circle:
        # A round bailey has no straight far wall, so the hall sits inside the
        # ring opposite the gate and shrinks until its corners clear the wall.
        direction = {"south": (0.0, 1.0), "north": (0.0, -1.0),
                     "west": (1.0, 0.0), "east": (-1.0, 0.0)}[entry_side]
        offset = keep_side / 2 + hall_depth / 2 + 1.5
        limit = radius - wall - 1.0
        while hall_width > 6.0 and math.hypot(hall_width / 2, offset + hall_depth / 2) > limit:
            hall_width -= 1.0
        hall_centre = (centre[0] + direction[0] * offset, centre[1] + direction[1] * offset)
        hall_rect = (hall_centre[0] - hall_width / 2, hall_centre[1] - hall_depth / 2,
                     hall_centre[0] + hall_width / 2, hall_centre[1] + hall_depth / 2)
    else:
        hall_y = (y0 + wall + 1.0) if entry_side == "north" else (y1 - wall - 1.0 - hall_depth)
        hall = ((x0 + x1) / 2 - hall_width / 2, hall_y,
                (x0 + x1) / 2 + hall_width / 2, hall_y + hall_depth)
        hall_rect = (max(hall[0], x0 + wall), max(hall[1], y0 + wall),
                     min(hall[2], x1 - wall), min(hall[3], y1 - wall))
    if hall_rect[2] - hall_rect[0] > 4.0 and hall_rect[3] - hall_rect[1] > 4.0:
        if not any(_overlaps(hall_rect, (v["x0"], v["y0"], v["x1"], v["y1"]))
                   for v in volumes if v["role"] == "keep"):
            hall_volume = part("hall", hall_rect, 10.0)
            # The great hall is one tall room, but it still needs a way in from
            # the bailey rather than four solid walls.
            hall_volume["door"] = {
                "side": entry_side,
                "width_m": round(min(2.2, _compound_side_span(hall_rect, entry_side) * 0.4), 3),
                "height_m": 3.0}
            volumes.append(hall_volume)
    height = max(v["height_m"] for v in volumes)
    return CompoundDesign(id=f"design_{site.id}", type=template.type, role=site.role,
                          design_state=site.design_state, site_id=site.id,
                          x0=round(x0, 3), y0=round(y0, 3), x1=round(x1, 3), y1=round(y1, 3),
                          entry_side=entry_side, volumes=tuple(volumes), height_m=round(height, 3),
                          materials=dict(pack.materials))


def validate_compound(design: CompoundDesign, site: Site) -> dict:
    """Independent checks on a compound: inside the site, capped, non-overlapping."""
    results: list[dict] = []

    def check(rule: str, passed: bool, message: str) -> None:
        results.append({"rule": rule, "state": "pass" if passed else "fail", "message": message})

    roles = [volume["role"] for volume in design.volumes]
    check("design.outline", site.x0 - 2e-3 <= design.x0 and design.x1 <= site.x1 + 2e-3
          and site.y0 - 2e-3 <= design.y0 and design.y1 <= site.y1 + 2e-3,
          f"bailey {round(design.area_m2)} m² inside the site")

    def ramp_reach_ok(volume: dict) -> bool:
        """A gate ramp may leave the site, but only towards its own street."""
        low = [site.x0 - 2e-3, site.y0 - 2e-3]
        high = [site.x1 + 2e-3, site.y1 + 2e-3]
        axis = 1 if design.entry_side in {"north", "south"} else 0
        if design.entry_side in {"south", "west"}:
            low[axis] -= RAMP_EXCURSION_M
        else:
            high[axis] += RAMP_EXCURSION_M
        return (low[0] <= volume["x0"] and volume["x1"] <= high[0]
                and low[1] <= volume["y0"] and volume["y1"] <= high[1])

    check("design.volumes_inside",
          all(ramp_reach_ok(v) if v["role"] in COMPOUND_RAMP_ROLES else
              (site.x0 - 2e-3 <= v["x0"] and v["x1"] <= site.x1 + 2e-3
               and site.y0 - 2e-3 <= v["y0"] and v["y1"] <= site.y1 + 2e-3)
              for v in design.volumes),
          f"{len(design.volumes)} volume(s) inside the site "
          f"(gate ramps may reach {RAMP_EXCURSION_M} m out on the entry side)")
    check("design.height", design.height_m <= site.max_height_m + 2e-3,
          f"{design.height_m} m against the envelope {site.max_height_m} m")
    check("design.parts", {"wall", "tower", "keep"} <= set(roles),
          f"a castle needs a wall, towers and a keep: {sorted(set(roles))}")
    check("design.interior_levels",
          all(0.0 < level < v["height_m"]
              for v in design.volumes for level in v.get("levels_m", ())),
          "every interior floor sits inside its own volume")
    check("design.interior_stair",
          all(v["x0"] - 2e-3 <= v["stair"]["x0"] and v["stair"]["x1"] <= v["x1"] + 2e-3
              and v["y0"] - 2e-3 <= v["stair"]["y0"] and v["stair"]["y1"] <= v["y1"] + 2e-3
              for v in design.volumes if "stair" in v),
          "the keep stair stays inside the keep")
    check("design.doors",
          all(v["door"]["width_m"] > 0.0 and v["door"]["height_m"] > 0.0
              for v in design.volumes if "door" in v),
          "every declared doorway has a positive size")
    gate_parts = [v for v in design.volumes if v["role"] == "gate"]
    lintels = [v for v in gate_parts if v["base_m"] >= GATE_OPENING_H_M - 1e-6]
    check("design.gatehouse",
          not gate_parts or (len(lintels) == 1 and len(gate_parts) == 3),
          f"gatehouse parts: {len(gate_parts)} gate volume(s), {len(lintels)} lintel(s)")
    check("design.gate_opening",
          all(v["base_m"] >= 3.0 for v in lintels),
          "the gateway clears three metres")
    # Wall segments are one continuous run — a polygonal ring's chords overlap at
    # the corners by construction — so only the distinct structures (towers,
    # keep, hall) have to stay clear of everything.
    # A gate lintel and its own threshold platform share a footprint but not a
    # height, and that is exactly how a gateway works, so the clash test is
    # three-dimensional: same plan *and* overlapping elevation.
    rects = [(v["role"], v["x0"], v["y0"], v["x1"], v["y1"], v["base_m"], v["height_m"])
             for v in design.volumes]

    def clash(a: tuple, b: tuple) -> bool:
        if "wall" in (a[0], b[0]):
            return False
        return (_overlaps(a[1:5], b[1:5])
                and min(a[6], b[6]) - max(a[5], b[5]) > 2e-3)

    overlap = any(clash(rects[i], rects[j])
                  for i in range(len(rects)) for j in range(i + 1, len(rects)))
    check("design.volumes_clear", not overlap,
          "no two structures overlap in plan and elevation "
          "(wall segments may overlap in their run)")
    return {"design_id": design.id, "type": design.type, "kind": "compound",
            "state": "pass" if all(item["state"] == "pass" for item in results) else "fail",
            "checks": results}


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
