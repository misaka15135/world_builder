from __future__ import annotations

import math
import random

from . import GENERATOR_VERSION
from .spec import PilotSpec, canonical, digest

STAGES = ("terrain", "network", "parcels", "buildings", "interiors")


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
    if abs(x - 64) <= 4:
        return -2.0
    amplitude = 0.8 if spec.scenario == "hillside" else 0.2
    return round(0.25 + amplitude * (x / 128) + 0.1 * math.sin(y / 20 + spec.seed % 31), 6)


def initial_records(spec: PilotSpec) -> list[dict]:
    root = entity(spec.world_id, "world", None, [0, 0, -4], [128, 128, 36])
    root["transform"]["translation"] = [0, 0, 0]
    records = [{
        "record_type": "world_spec", "id": "spec_pilot", "source_prompt": spec.source_prompt,
        "world_seed": f"0x{spec.seed:016x}", "region_bounds": {"min": [0, 0, -4], "max": [128, 128, 32]},
        "style_profile": "arcane_pilot_v1", "target_profile_ids": [], "fantasy_exceptions": [],
        "extensions": {"pilot_spec": spec.to_dict(), "generator_version": GENERATOR_VERSION, "stage": "initial",
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
    if stage == "terrain":
        values = [[height(spec, x, y) for x in range(0, 129, 4)] for y in range(0, 129, 4)]
        payload = canonical({"version": 1, "unit": "m", "axes": "RH_X_east_Y_north_Z_up",
                             "origin": [0, 0], "spacing_m": 4, "heights": values})
        checksum = digest({"version": 1, "unit": "m", "axes": "RH_X_east_Y_north_Z_up",
                           "origin": [0, 0], "spacing_m": 4, "heights": values})
        resources["asset_heightfield"] = payload
        terrain = entity("terrain_main", "terrain", world, [0, 0, -2], [128, 128, 4])
        terrain["geometry"] = {"representation": "heightfield", "asset_id": "asset_heightfield", "spacing_m": 4}
        river = entity("river_main", "river", world, [60, 0, -2], [8, 128, 2])
        river["geometry"] = {"representation": "channel", "centerline_m": [[64, 0, 0], [64, 128, 0]], "width_m": 8, "water_level_m": 0}
        additions = [terrain, river, {"record_type": "asset", "id": "asset_heightfield", "content_hash": checksum,
            "uri": "assets/sha256/" + checksum[7:], "media_type": "application/json", "length_unit": "m",
            "axis": "RH_Z_up", "license": {"spdx": "LicenseRef-Generated", "source": GENERATOR_VERSION},
            "bounds": terrain["bounds"], "extensions": {"role": "heightfield"}}]
    elif stage == "network":
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
        for i, lot in enumerate(lots):
            rng = random.Random(int(digest([spec.seed, lot["id"], GENERATOR_VERSION])[7:23], 16))
            lot_origin = lot["bounds"]["min"]
            building = entity(f"building_{i:03d}", "building", lot["id"], [8, 6, 2], [16, 16, 6.4],
                              parent_origin=lot_origin, storeys=2, interior_state="deferred",
                              roof_style=rng.choice(["gable", "spire"]), style_profile="arcane_pilot_v1")
            building["semantic_completeness"] = "shell_only"
            building["geometry"].update({"representation": "parametric_building", "storey_height_m": 3,
                "wall_thickness_m": 0.2, "floor_thickness_m": 0.2, "roof_height_m": 0.4,
                "stair_void_local_m": {"min": [11, 3, 3], "max": [14, 9 if spec.layout_profile == "compact" else 13, 3.2]},
                "entry": {"side": "east" if i % 2 == 0 else "west", "offset_m": 2, "width_m": 2, "height_m": 2.4}})
            if spec.lock_stair_void:
                building["locks"].append({"json_pointer": "/geometry/stair_void_local_m", "mode": "subtree", "reason": "user locked the initial stair reservation"})
            additions.append(building)
            x0, y0, _ = building["bounds"]["min"]
            start, end = (x0 + 16, 46) if i % 2 == 0 else (82, x0)
            additions.append(entity(f"access_{i:03d}", "road", world, [start, y0 + 1, 1.6], [end-start, 2, 0.4], surface_z_m=2))
            additions.extend([relation(f"relation_access_road_{i:03d}", "connects", f"access_{i:03d}", ["road_west" if i % 2 == 0 else "road_east"]),
                              relation(f"relation_building_access_{i:03d}", "entrance", building["id"], [f"access_{i:03d}"])])
    elif stage == "interiors":
        buildings = sorted((r for r in records if r.get("kind") == "building"), key=lambda r: r["id"])
        for i, building in enumerate(buildings[:spec.interior_count]):
            origin = building["bounds"]["min"]
            building["attributes"]["interior_state"] = "generated"
            building["semantic_completeness"] = "component"
            room_ids = []
            for floor in range(2):
                floor_id, room_id = f"storey_{i:03d}_{floor}", f"room_{i:03d}_{floor}"
                storey = entity(floor_id, "storey", building["id"], [0, 0, floor*3], [16, 16, 3], parent_origin=origin)
                room = entity(room_id, "room", floor_id, [1, 1, 0.2], [9, 14, 2.6], parent_origin=storey["bounds"]["min"])
                furniture = entity(f"furniture_{i:03d}_{floor}", "furniture", room_id, [2, 5, 0], [1, 1, 1], parent_origin=room["bounds"]["min"], use="reading_table")
                room_ids.append(room_id)
                additions.extend([storey, room, furniture])
            run = 4 if spec.layout_profile == "compact" else 8
            stair = entity(f"stair_{i:03d}", "stair", building["id"], [11, 3, 0.2], [3, run+2, 5.6], parent_origin=origin)
            stair["geometry"] = {"representation": "straight_stair", "size_m": [3, run+2, 5.6], "rise_m": 3,
                                 "run_m": run, "clear_width_m": 2, "headroom_m": 2.4,
                                 "steps": 20, "landing_length_m": 2, "floor_levels_m": [2.2, 5.2]}
            additions.extend([stair, relation(f"relation_stair_{i:03d}", "connects", stair["id"], room_ids)])
    else:
        raise ValueError(f"unknown stage {stage}")
    return additions, resources
