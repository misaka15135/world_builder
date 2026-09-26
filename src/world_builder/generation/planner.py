from __future__ import annotations

import math
import random

from . import GENERATOR_VERSION
from .spec import PilotSpec, canonical, digest

STAGES = ("terrain", "network", "parcels", "buildings", "interiors")

# Per-building programmes for the 512 m city. Each programme decides how a
# storey is divided and what furniture the rooms hold; the shapes stay template
# driven, so everything below is adapter-side policy, not recovered source data.
PROGRAMMES = ("residence", "shop", "workshop", "library", "inn", "temple", "town_hall", "apartment", "office")
PROGRAMME_ROOMS = {
    "residence": ("living_room", "bedroom"),
    "shop": ("shopfront", "stockroom"),
    "workshop": ("workshop", "tool_store"),
    "library": ("reading_room", "book_stack"),
    "inn": ("common_room", "guest_room"),
    "temple": ("nave", "vestry"),
    "town_hall": ("council_chamber", "records_room"),
    "apartment": ("living_room", "bedroom"),
    "office": ("open_plan", "meeting_room"),
}
PROGRAMME_FURNITURE = {
    "living_room": ("hearth", "bench"),
    "bedroom": ("bed",),
    "shopfront": ("counter", "display_rack"),
    "stockroom": ("crate_stack",),
    "workshop": ("workbench", "anvil"),
    "tool_store": ("tool_rack",),
    "reading_room": ("reading_table", "chair"),
    "book_stack": ("shelf", "shelf"),
    "common_room": ("long_table", "bench"),
    "guest_room": ("bed", "chest"),
    "nave": ("altar", "pew"),
    "vestry": ("cabinet",),
    "council_chamber": ("long_table", "chair"),
    "records_room": ("shelf", "shelf"),
    "open_plan": ("desk", "desk"),
    "meeting_room": ("long_table", "chair"),
}
FURNITURE_SIZES_M = {
    "hearth": [1.6, 0.8, 1.0], "bench": [1.6, 0.6, 0.5], "bed": [1.0, 2.0, 0.6],
    "counter": [1.8, 0.8, 1.0], "display_rack": [1.0, 0.6, 1.6], "crate_stack": [1.0, 1.0, 1.2],
    "workbench": [1.8, 0.8, 0.9], "anvil": [0.8, 0.6, 0.8], "tool_rack": [1.2, 0.4, 1.6],
    "reading_table": [1.4, 0.9, 0.8], "chair": [0.6, 0.6, 0.9], "shelf": [1.6, 0.4, 1.8],
    "long_table": [2.2, 0.9, 0.8], "chest": [0.9, 0.6, 0.7],
    "altar": [1.6, 0.9, 1.2], "pew": [2.0, 0.6, 0.9], "cabinet": [1.0, 0.5, 1.6],
    "desk": [1.6, 0.8, 0.75],
}

# Silhouette follows function: the roof style and its height are declared per
# programme instead of being drawn at random, so a temple, a shop and a house
# do not share one outline.
PROGRAMME_ROOF = {
    "residence": ("gable", 1.2),
    "shop": ("flat", 0.4),
    "workshop": ("flat", 0.4),
    "library": ("spire", 2.4),
    "inn": ("gable", 1.6),
    "temple": ("spire", 3.0),
    "town_hall": ("gable", 2.0),
}

# Districts differ before individual buildings do: the plan below decides how
# wide, how tall and what kind of programme a district's buildings draw from,
# so the residential edge, the market band and the civic centre do not look
# alike. Layout regularity, road width and per-era style are still open work.
DISTRICT_PLAN = {
    "residential": {"road_width_m": 3, "parcel_jitter_m": 6, "width_m": (10, 12, 14), "depth_m": (14, 16), "storeys": (1, 2),
                    "programmes": ("residence", "residence", "workshop")},
    "market": {"road_width_m": 4, "parcel_jitter_m": 3, "width_m": (14, 16), "depth_m": (14, 16, 18), "storeys": (2, 2),
               "programmes": ("shop", "shop", "workshop", "inn")},
    "civic": {"road_width_m": 6, "parcel_jitter_m": 0, "width_m": (16, 18, 18), "depth_m": (16, 18, 18), "storeys": (2, 3),
              "programmes": ("library", "inn", "temple", "town_hall", "workshop")},
}
DISTRICT_USES = ("residential", "market", "civic")

# The style profile decides what the same three districts look like. The arcane
# profile is the original pitched-roof town; the modern profile trades pitched
# roofs and jittered lots for flat-roofed slabs on a strict grid, which is what
# a CBD next to low-rise housing should read as.
MODERN_DISTRICT_PLAN = {
    "residential": {"road_width_m": 4, "parcel_jitter_m": 0, "width_m": (14, 16, 18), "depth_m": (16, 18),
                    "storeys": (2, 3), "programmes": ("apartment", "apartment", "shop")},
    "market": {"road_width_m": 5, "parcel_jitter_m": 0, "width_m": (16, 18), "depth_m": (16, 18),
               "storeys": (3, 4), "programmes": ("shop", "office", "inn")},
    "civic": {"road_width_m": 8, "parcel_jitter_m": 0, "width_m": (18, 18), "depth_m": (18, 18),
              "storeys": (4, 5), "programmes": ("office", "office", "library")},
}
STYLE_DISTRICT_PLAN = {"arcane_medieval": DISTRICT_PLAN, "modern_grid": MODERN_DISTRICT_PLAN}
MODERN_ROOF = {"apartment": ("flat", 0.4), "shop": ("flat", 0.4), "office": ("flat", 0.4),
               "inn": ("flat", 0.4), "library": ("flat", 0.4), "workshop": ("flat", 0.4),
               "residence": ("flat", 0.4), "temple": ("flat", 0.4), "town_hall": ("flat", 0.4)}
STYLE_ROOF = {"arcane_medieval": PROGRAMME_ROOF, "modern_grid": MODERN_ROOF}


def storey_setbacks(width: float, depth: float, storeys: int, void: dict, style: str) -> list[list[float]]:
    """Per-storey setbacks in metres, ordered west/east/south/north.

    A building that keeps one footprint from the ground slab to the roof reads
    as a box no matter how good its roof is, so the upper storeys step back.
    The ground storey never moves — the entrance and the street edge sit on its
    outline — and the east side never moves either, because that strip holds the
    declared stair reservation. The remaining three sides step back as far as
    the plan allows, capped at two metres so the outline stays legible at 1 m =
    1 block. Setbacks are whole metres: a half-metre step would vanish when the
    export quantises to blocks.
    """
    setbacks = [[0.0, 0.0, 0.0, 0.0] for _ in range(storeys)]
    if storeys < 3:
        return setbacks
    cap = min(2.0, width - 9.0, depth / 2 - 3.0, depth - void["max"][1])
    step = float(int(max(0.0, math.floor(cap))))
    if step < 1.0:
        return setbacks
    # The arcane profile steps back once, an attic storey over a full-width
    # ground floor; the modern profile tapers over two storeys like a CBD
    # crown, which is the silhouette the style is supposed to read as.
    if style == "modern_grid" and storeys >= 4:
        setbacks[-1] = [step, 0.0, step, step]
        if storeys >= 5:
            setbacks[-2] = [min(1.0, step), 0.0, min(1.0, step), min(1.0, step)]
    else:
        setbacks[-1] = [min(1.0, step), 0.0, min(1.0, step), min(1.0, step)]
    return setbacks


def entity(entity_id: str, kind: str, parent: str | None, origin: list,
           size: list, parent_origin=(0, 0, 0), **attributes) -> dict:
    minimum = [round(origin[i] + parent_origin[i], 6) for i in range(3)]
    maximum = [round(minimum[i] + size[i], 6) for i in range(3)]
    chunks = [f"chunk_{x}_{y}" for x in range(max(0, int(minimum[0] // 64)), max(0, math.ceil(maximum[0] / 64) - 1) + 1)
              for y in range(max(0, int(minimum[1] // 64)), max(0, math.ceil(maximum[1] / 64) - 1) + 1)]
    return {
        "record_type": "entity", "id": entity_id, "kind": kind, "parent_id": parent,
        "chunk_ids": chunks, "transform": {"translation": origin, "rotation_xyzw": [0, 0, 0, 1], "scale": [1, 1, 1]},
        "bounds": {"min": minimum, "max": maximum}, "generation_state": "materialized",
        "semantic_completeness": "spatial", "attributes": attributes,
        "geometry": {"representation": "box", "size_m": size}, "constraint_ids": [], "recipe_id": None,
        "locks": [], "provenance": {"source": "generator", "created_by": GENERATOR_VERSION}, "extensions": {},
    }


def relation(record_id: str, kind: str, source: str, targets: list[str]) -> dict:
    return {"record_type": "relation", "id": record_id, "relation_type": kind,
            "source_id": source, "target_ids": targets, "attributes": {}, "extensions": {}}


def height(spec: PilotSpec, x: float, y: float) -> float:
    """Synthetic heightfield, metres; no hydrological simulation."""
    if abs(x - spec.region_size_m / 2) <= 4:
        return -2.0
    amplitude = 0.8 if spec.scenario == "hillside" else 0.2
    return round(0.25 + amplitude * (x / spec.region_size_m) + 0.1 * math.sin(y / 20 + spec.seed % 31), 6)


def initial_records(spec: PilotSpec) -> list[dict]:
    size = spec.region_size_m
    root = entity(spec.world_id, "world", None, [0, 0, -4], [size, size, 36])
    root["transform"]["translation"] = [0, 0, 0]
    root["provenance"]["created_by"] = spec.generator_version
    records = [{
        "record_type": "world_spec", "id": "spec_city" if size == 512 else "spec_pilot", "source_prompt": spec.source_prompt,
        "world_seed": f"0x{spec.seed:016x}", "region_bounds": {"min": [0, 0, -4], "max": [size, size, 32]},
        "style_profile": "arcane_city_template_v1" if size == 512 else "arcane_pilot_v1", "target_profile_ids": [], "fantasy_exceptions": [],
        "extensions": {spec.contract_key: spec.to_dict(), "generator_version": spec.generator_version, "stage": "initial",
                       "accepted_model_response_hash": spec.accepted_response_hash,
                       "model_provenance": spec.model_provenance},
    }, root]
    if spec.accepted_response_hash:
        records.append({"record_type": "asset", "id": "asset_model_response", "content_hash": spec.accepted_response_hash,
            "uri": "assets/sha256/" + spec.accepted_response_hash[7:], "media_type": "application/json",
            "length_unit": "m", "axis": "RH_Z_up",
            "license": {"spdx": "LicenseRef-GeneratedModelResponse", "source": spec.model_provenance["provider_id"]},
            "bounds": {"min": [0, 0, 0], "max": [0, 0, 0]},
            "extensions": {"role": "accepted_model_response", "model_id": spec.model_provenance["model_id"]}})
    return records


def plan_stage(spec: PilotSpec, stage: str, records: list[dict]) -> tuple[list[dict], dict[str, bytes]]:
    """Pure candidate construction. World root has an identity transform."""
    additions: list[dict] = []
    resources: dict[str, bytes] = {}
    world = spec.world_id
    size = spec.region_size_m
    style = getattr(spec, "style_profile", "arcane_medieval")
    district_plan = STYLE_DISTRICT_PLAN[style]
    style_roof = STYLE_ROOF[style]
    center = size // 2
    if stage == "terrain":
        values = [[height(spec, x, y) for x in range(0, size + 1, 4)] for y in range(0, size + 1, 4)]
        payload = canonical({"version": 1, "unit": "m", "axes": "RH_X_east_Y_north_Z_up",
                             "origin": [0, 0], "spacing_m": 4, "heights": values})
        checksum = digest({"version": 1, "unit": "m", "axes": "RH_X_east_Y_north_Z_up",
                           "origin": [0, 0], "spacing_m": 4, "heights": values})
        resources["asset_heightfield"] = payload
        terrain = entity("terrain_main", "terrain", world, [0, 0, -2], [size, size, 4])
        terrain["geometry"] = {"representation": "heightfield", "asset_id": "asset_heightfield", "spacing_m": 4}
        river = entity("river_main", "river", world, [center - 4, 0, -2], [8, size, 2])
        river["geometry"] = {"representation": "channel", "centerline_m": [[center, 0, 0], [center, size, 0]], "width_m": 8, "water_level_m": 0}
        additions = [terrain, river, {"record_type": "asset", "id": "asset_heightfield", "content_hash": checksum,
            "uri": "assets/sha256/" + checksum[7:], "media_type": "application/json", "length_unit": "m",
            "axis": "RH_Z_up", "license": {"spdx": "LicenseRef-Generated", "source": spec.generator_version},
            "bounds": terrain["bounds"], "extensions": {"role": "heightfield"}}]
    elif stage == "network":
        if size == 512:
            x_pitch, y_pitch = (42, 52) if spec.scenario == "dense" else (44, 56)
            cross_y = 44 + 4 * y_pitch
            west_spines = [40 + col * x_pitch for col in range(5)]
            east_spines = [324 + col * x_pitch for col in range(5)]
            # Each spine is split by district so the street itself gets wider
            # towards the centre instead of one fixed 4 m ribbon.
            bands = ((0, 3 * y_pitch), (3 * y_pitch, 6 * y_pitch), (6 * y_pitch, size))
            for bank, xs in (("west", west_spines), ("east", east_spines)):
                for col, x in enumerate(xs):
                    for d, (n0, n1) in enumerate(bands):
                        n0, n1 = max(8, n0), min(size - 8, n1)
                        additions.append(entity(f"road_{bank}_{col}_{d}", "road", world,
                                                [x, n0, 1.6], [district_plan[DISTRICT_USES[d]]["road_width_m"], n1 - n0, 0.4],
                                                surface_z_m=2))
                    additions.append(relation(f"relation_{bank}_{col}_cross", "connects",
                                              f"road_{bank}_{col}_1", [f"road_cross_{bank}"]))
            additions.extend([
                entity("road_cross_west", "road", world, [west_spines[0], cross_y, 1.6], [center - 4 - west_spines[0], 6, 0.4], surface_z_m=2),
                entity("road_cross_east", "road", world, [center + 4, cross_y, 1.6], [east_spines[-1] + 4 - center - 4, 6, 0.4], surface_z_m=2),
                entity("bridge_main", "bridge", world, [center - 4, cross_y, 1.6], [8, 6, 0.4], surface_z_m=2),
                relation("relation_bridge_river", "crosses", "bridge_main", ["river_main"]),
                relation("relation_bridge_west", "connects", "road_cross_west", ["bridge_main"]),
                relation("relation_bridge_east", "connects", "bridge_main", ["road_cross_east"]),
            ])
            if style == "arcane_medieval":
                # A city wall is part of the arcane profile only. Gates sit on
                # the cross street's latitude and short approach roads tie them
                # to the street network, so the wall never isolates the city.
                g0, g1 = cross_y - 3, cross_y + 3
                additions.extend([
                    entity("wall_west_south", "wall", world, [0, 0, 0], [2, g0, 8], shell="stone_wall"),
                    entity("wall_west_north", "wall", world, [0, g1, 0], [2, size - g1, 8], shell="stone_wall"),
                    entity("wall_east_south", "wall", world, [size - 2, 0, 0], [2, g0, 8], shell="stone_wall"),
                    entity("wall_east_north", "wall", world, [size - 2, g1, 0], [2, size - g1, 8], shell="stone_wall"),
                    entity("wall_south", "wall", world, [0, 0, 0], [size, 2, 8], shell="stone_wall"),
                    entity("wall_north", "wall", world, [0, size - 2, 0], [size, 2, 8], shell="stone_wall"),
                    entity("approach_west", "road", world, [2, g0, 1.6], [west_spines[0] - 2, 6, 0.4], surface_z_m=2),
                    entity("approach_east", "road", world, [east_spines[-1] + 4, g0, 1.6], [size - 2 - east_spines[-1] - 4, 6, 0.4], surface_z_m=2),
                    relation("relation_wall_gate_west", "connects", "approach_west", ["road_cross_west"]),
                    relation("relation_wall_gate_east", "connects", "approach_east", ["road_cross_east"]),
                ])
        else:
            additions = [
            entity("road_west", "road", world, [44, 8, 1.6], [4, 112, 0.4], surface_z_m=2),
            entity("road_east", "road", world, [80, 8, 1.6], [4, 112, 0.4], surface_z_m=2),
            entity("road_cross_west", "road", world, [44, 61, 1.6], [16, 6, 0.4], surface_z_m=2),
            entity("road_cross_east", "road", world, [68, 61, 1.6], [16, 6, 0.4], surface_z_m=2),
            entity("bridge_main", "bridge", world, [60, 61, 1.6], [8, 6, 0.4], surface_z_m=2),
            relation("relation_bridge_river", "crosses", "bridge_main", ["river_main"]),
            relation("relation_west_cross", "connects", "road_west", ["road_cross_west"]),
            relation("relation_bridge_west", "connects", "road_cross_west", ["bridge_main"]),
            relation("relation_bridge_east", "connects", "bridge_main", ["road_cross_east"]),
            relation("relation_east_cross", "connects", "road_cross_east", ["road_east"]),
            ]
    elif stage == "parcels":
        if size == 512:
            x_pitch, y_pitch = (42, 52) if spec.scenario == "dense" else (44, 56)
            boundaries = (0, 3 * y_pitch, 6 * y_pitch, size)
            for district, use in enumerate(("residential", "market", "civic")):
                additions.append(entity(f"district_{district}", "district", world,
                                        [0, boundaries[district], -4], [size, boundaries[district + 1] - boundaries[district], 36], use=use))
            for row in range(8):
                district = min(row // 3, 2)
                y = 8 + row * y_pitch
                for bank in range(2):
                    for col in range(5):
                        i = row * 10 + bank * 5 + col
                        x = (8 if bank == 0 else 292) + col * x_pitch
                        # Outlying districts sit on a looser grid than the civic
                        # centre: only the north offset moves, so the spine and
                        # access roads keep their geometry.
                        jitter = district_plan[DISTRICT_USES[district]]["parcel_jitter_m"]
                        py = y
                        if jitter:
                            rng = random.Random(int(digest([spec.seed, f"parcel_{i:03d}", spec.generator_version])[7:23], 16))
                            py = y + rng.uniform(-jitter, jitter)
                        additions.append(entity(f"parcel_{i:03d}", "parcel", f"district_{district}",
                                                [x, py - boundaries[district], 4], [32, 32, 24],
                                                parent_origin=[0, boundaries[district], -4], bank=bank, column=col,
                                                raw_height_range_m=[height(spec, x, py), height(spec, x + 32, py + 32)],
                                                platform_z_m=2, construction="level_platform_with_foundation"))
        else:
            pitch, inset = (32, 2) if spec.scenario == "dense" else (40, 8)
            for row, use in enumerate(("residential", "market", "civic")):
                additions.append(entity(f"district_{row}", "district", world, [0, row * pitch, -4], [128, pitch, 36], use=use))
            for i in range(spec.building_count):
                row, bank = divmod(i, 2)
                x, y = (8 if bank == 0 else 88), inset + row * pitch
                lot = entity(f"parcel_{i:03d}", "parcel", f"district_{row}", [x, inset, 4], [32, 28, 12],
                             parent_origin=[0, row * pitch, -4], bank=bank,
                             raw_height_range_m=[height(spec, x, y), height(spec, x + 32, y + 28)],
                             platform_z_m=2, construction="level_platform_with_foundation")
                additions.append(lot)
    elif stage == "buildings":
        lots = sorted((r for r in records if r.get("kind") == "parcel"), key=lambda r: r["id"])
        district_use = {r["id"]: r["attributes"].get("use") for r in records if r.get("kind") == "district"}
        for i, lot in enumerate(lots):
            rng = random.Random(int(digest([spec.seed, lot["id"], spec.generator_version])[7:23], 16))
            lot_origin = lot["bounds"]["min"]
            if size == 512:
                plan = district_plan.get(district_use.get(lot["parent_id"]), district_plan["residential"])
                width = rng.choice(plan["width_m"])
                depth = rng.choice(plan["depth_m"])
                storeys = rng.choice(plan["storeys"])
                programme = rng.choice(plan["programmes"])
                roof_style, roof_height = style_roof[programme]
                origin = [(32 - width) / 2, (32 - depth) / 2, 2]
                box = [width, depth, storeys * 3 + roof_height]
            else:
                width = depth = 16
                storeys, programme = 2, "residence"
                roof_style, roof_height = "gable", 0.4
                origin, box = [8, 6, 2], [16, 16, 6.4]
            building = entity(f"building_{i:03d}", "building", lot["id"], origin, box,
                              parent_origin=lot_origin, storeys=storeys, interior_state="deferred",
                              programme=programme, roof_style=roof_style,
                              style_profile="arcane_city_template_v1" if size == 512 else "arcane_pilot_v1")
            building["semantic_completeness"] = "shell_only"
            void = {"min": [width - 5, 3, 3],
                    "max": [width - 2, 9 if spec.layout_profile == "compact" else 13, 3.2]}
            building["geometry"].update({"representation": "parametric_building", "storey_height_m": 3,
                "wall_thickness_m": 0.2, "floor_thickness_m": 0.2, "roof_height_m": roof_height,
                "stair_void_local_m": void,
                "entry": {"side": "east" if size == 512 or i % 2 == 0 else "west", "offset_m": 2, "width_m": 2, "height_m": 2.4}})
            if size == 512:
                # The frozen 128 m pilot keeps its single full-width outline.
                building["geometry"]["storey_insets_local_m"] = storey_setbacks(width, depth, storeys, void, style)
                # The roof style and height are shape, not just a label, and the
                # target adapters read geometry. Declaring the style here as
                # well as in the attributes is what lets a gable or spire
                # actually leave a stepped roof instead of a flat slab.
                building["geometry"]["roof_style"] = roof_style
            if spec.lock_stair_void:
                building["locks"].append({"json_pointer": "/geometry/stair_void_local_m", "mode": "subtree", "reason": "user locked the initial stair reservation"})
            additions.append(building)
            x0, y0, _ = building["bounds"]["min"]
            if size == 512:
                start, end = x0 + width, lot_origin[0] + 32
                district_index = int(lot["parent_id"].split("_")[1])
                road_id = (f"road_{'west' if lot['attributes']['bank'] == 0 else 'east'}"
                           f"_{lot['attributes']['column']}_{district_index}")
            else:
                start, end = (x0 + 16, 46) if i % 2 == 0 else (82, x0)
                road_id = "road_west" if i % 2 == 0 else "road_east"
            additions.append(entity(f"access_{i:03d}", "road", world, [start, y0 + 1, 1.6], [end-start, 2, 0.4], surface_z_m=2))
            additions.extend([relation(f"relation_access_road_{i:03d}", "connects", f"access_{i:03d}", [road_id]),
                              relation(f"relation_building_access_{i:03d}", "entrance", building["id"], [f"access_{i:03d}"])])
    elif stage == "interiors":
        buildings = sorted((r for r in records if r.get("kind") == "building"), key=lambda r: r["id"])
        for i, building in enumerate(buildings[:spec.interior_count]):
            origin = building["bounds"]["min"]
            if size != 512:
                # The frozen 128 m pilot keeps its original single-room plan.
                building["attributes"]["interior_state"] = "generated"
                building["semantic_completeness"] = "component"
                room_ids = []
                for floor in range(2):
                    floor_id, room_id = f"storey_{i:03d}_{floor}", f"room_{i:03d}_{floor}"
                    storey = entity(floor_id, "storey", building["id"], [0, 0, floor * 3], [16, 16, 3], parent_origin=origin)
                    room = entity(room_id, "room", floor_id, [1, 1, 0.2], [9, 14, 2.6], parent_origin=storey["bounds"]["min"])
                    furniture = entity(f"furniture_{i:03d}_{floor}", "furniture", room_id, [2, 5, 0], [1, 1, 1], parent_origin=room["bounds"]["min"], use="reading_table")
                    room_ids.append(room_id)
                    additions.extend([storey, room, furniture])
                run = 4 if spec.layout_profile == "compact" else 8
                stair = entity(f"stair_{i:03d}", "stair", building["id"], [11, 3, 0.2], [3, run + 2, 5.6], parent_origin=origin)
                stair["geometry"] = {"representation": "straight_stair", "size_m": [3, run + 2, 5.6], "rise_m": 3,
                                     "run_m": run, "clear_width_m": 2, "headroom_m": 2.4,
                                     "steps": 20, "landing_length_m": 2, "floor_levels_m": [2.2, 5.2]}
                additions.extend([stair, relation(f"relation_stair_{i:03d}", "connects", stair["id"], room_ids)])
                continue
            width, depth, _ = building["geometry"]["size_m"]
            storeys = building["attributes"]["storeys"]
            programme = building["attributes"].get("programme", "residence")
            void = building["geometry"]["stair_void_local_m"]
            insets = building["geometry"].get("storey_insets_local_m") or [[0.0, 0.0, 0.0, 0.0]] * storeys
            building["attributes"]["interior_state"] = "generated"
            building["semantic_completeness"] = "component"
            for floor in range(storeys):
                floor_id = f"storey_{i:03d}_{floor}"
                west, east, south, north = insets[floor]
                # The storey outline is the building outline minus that
                # storey's setback, so an inset upper floor automatically
                # carries smaller rooms instead of a room hanging outside it.
                span_x, span_n = round(width - west - east, 6), round(depth - south - north, 6)
                storey = entity(floor_id, "storey", building["id"], [west, south, floor * 3],
                                [span_x, span_n, 3], parent_origin=origin)
                additions.append(storey)
                # The stair keeps the east strip; the rest of the storey splits
                # into two rooms along the north axis.
                block_x0, block_x1 = west + 1.0, void["min"][0] - 1.0
                mid = (south + depth - north) / 2
                uses = PROGRAMME_ROOMS.get(programme, PROGRAMME_ROOMS["residence"])
                # The two rooms leave a one-metre slot between them for the
                # declared partition, so the wall occupies neither room.
                for k, (n0, n1) in enumerate(((south + 1.0, mid - 1.0), (mid, depth - north - 1.0))):
                    use = uses[(floor + k) % len(uses)]
                    room_id = f"room_{i:03d}_{floor}_{k}"
                    room = entity(room_id, "room", floor_id, [round(block_x0 - west, 6), round(n0 - south, 6), 0.2],
                                  [round(block_x1 - block_x0, 6), round(n1 - n0, 6), 2.6],
                                  parent_origin=storey["bounds"]["min"], use=use)
                    additions.append(room)
                    room_w = round(block_x1 - block_x0, 6)
                    room_d = round(n1 - n0, 6)
                    for f, item in enumerate(PROGRAMME_FURNITURE[use]):
                        piece_size = list(FURNITURE_SIZES_M[item])
                        # Keep every piece inside its room: narrow residential
                        # rooms cannot take the default wall offset.
                        ox = min(1.0, max(0.2, room_w - piece_size[0] - 0.2))
                        on = min(1.0 + 2.0 * f, max(0.2, room_d - piece_size[1] - 0.2))
                        additions.append(entity(f"furniture_{i:03d}_{floor}_{k}_{f}", "furniture", room_id,
                                                [round(ox, 6), round(on, 6), 0.0], piece_size,
                                                parent_origin=room["bounds"]["min"], use=item))
                # The wall between the two rooms is source data, not an adapter
                # invention, so every target derives the same circulation. Its
                # opening carries the doorway the adapter has to leave clear.
                partition = entity(f"partition_{i:03d}_{floor}", "partition", floor_id,
                                   [round(block_x0 - west, 6), round(mid - 1.0 - south, 6), 0.2],
                                   [round(block_x1 - block_x0, 6), 1.0, 2.6],
                                   parent_origin=storey["bounds"]["min"],
                                   opening={"side": "west", "width_m": 2.0, "height_m": 2.0})
                additions.append(partition)
            if storeys >= 2:
                run = 4 if spec.layout_profile == "compact" else 8
                stair = entity(f"stair_{i:03d}", "stair", building["id"], [void["min"][0], 3, 0.2], [3, run + 2, 5.6], parent_origin=origin)
                stair["geometry"] = {"representation": "straight_stair", "size_m": [3, run + 2, 5.6], "rise_m": 3,
                                     "run_m": run, "clear_width_m": 2, "headroom_m": 2.4,
                                     "steps": 20, "landing_length_m": 2, "floor_levels_m": [2.2, 5.2]}
                additions.extend([stair, relation(f"relation_stair_{i:03d}", "connects", stair["id"],
                                                  [f"room_{i:03d}_0_0", f"room_{i:03d}_1_0"])])
    else:
        raise ValueError(f"unknown stage {stage}")
    for item in additions:
        if item["record_type"] == "entity":
            item["provenance"]["created_by"] = spec.generator_version
    return additions, resources
