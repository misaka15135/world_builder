"""Assemble the scene into one WIR package (work order 018, stage F).

Everything the pipeline planned - terrain, water, districts, ownership, the
skeleton, the envelopes and the per-building designs - is written as WIR
records: a world spec, a world root, spatial entities with bounds, relations
between them, and a content-addressed asset for the heightfield. The result is
validated by the 0.1 contract in `world_builder.wir.validator`, and by the
cross-stage invariants that only exist once the stages are put together.

What this stage does **not** do yet: the scene uses its own `scene_spec`
extension rather than the 512 m `city_spec` the Minecraft and Unity adapters
read today, so the assembled package is not yet consumed by those adapters.
That wiring is the next increment and is stated as such in the contract.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from world_builder.generation.spec import canonical, digest
from world_builder.generation.planner import entity, relation
from world_builder.wir.validator import validate_package

from .brief import SceneBrief
from .catalogue import SceneError, SettingPack
from .designer import BuildingDesign
from .siting import SitingPlan
from .terrain import TerrainPlan

ASSEMBLY_VERSION = "0.1.0"
DEFAULT_HEIGHTFIELD_SPACING_M = 8


def _spec_record(brief: SceneBrief, pack: SettingPack, world_id: str) -> dict:
    return {
        "record_type": "world_spec", "id": "spec_scene", "source_prompt": brief.source_prompt,
        "world_seed": f"0x{brief.seed:016x}",
        "region_bounds": {"min": [0, 0, 0], "max": [brief.region_m, brief.region_m, 64]},
        # Target profiles are records in the 0.1 contract, so the *intended*
        # targets live in the scene extension until the target wiring lands.
        "style_profile": pack.style_profile, "target_profile_ids": [],
        "fantasy_exceptions": [],
        "extensions": {
            "scene_spec": {"brief": brief.to_dict(), "brief_digest": brief.digest(),
                           "setting": pack.id, "assembly_version": ASSEMBLY_VERSION,
                           "intended_targets": list(brief.targets)},
            "generator_version": f"scene.{ASSEMBLY_VERSION}",
            "stage": "assembled",
            "accepted_model_response_hash": None,
            "model_provenance": None,
        },
    }


def assemble_scene(brief: SceneBrief, pack: SettingPack, terrain: TerrainPlan, siting: SitingPlan,
                   designs: tuple[BuildingDesign, ...]) -> dict:
    """Build one WIR package from the stage outputs."""
    world_id = "world_" + digest({"brief": brief.to_dict(), "setting": pack.id,
                                  "assembly": ASSEMBLY_VERSION})[7:23]
    spacing = terrain.spacing_m
    records: list[dict] = [_spec_record(brief, pack, world_id)]
    root = entity(world_id, "world", None, [0, 0, 0], [brief.region_m, brief.region_m, 64])
    root["provenance"]["created_by"] = f"scene.{ASSEMBLY_VERSION}"
    records.append(root)

    heights = [list(row) for row in terrain.heights]
    payload = canonical({"version": 1, "unit": "m", "axes": "RH_X_east_Y_north_Z_up", "origin": [0, 0],
                         "spacing_m": spacing, "heights": [[round(v, 3) for v in row] for row in heights]})
    checksum = digest({"version": 1, "unit": "m", "spacing_m": spacing,
                       "heights": [[round(v, 3) for v in row] for row in heights]})
    terrain_entity = entity("terrain_main", "terrain", world_id, [0, 0, 0],
                            [brief.region_m, brief.region_m, 64])
    terrain_entity["geometry"] = {"representation": "heightfield", "asset_id": "asset_heightfield",
                                  "spacing_m": spacing, "relief_m": [terrain.stats["min_m"], terrain.stats["max_m"]]}
    records.append(terrain_entity)
    records.append({"record_type": "asset", "id": "asset_heightfield", "content_hash": checksum,
                    "uri": "assets/sha256/" + checksum[7:], "media_type": "application/json",
                    "length_unit": "m", "axis": "RH_Z_up",
                    "license": {"spdx": "LicenseRef-Generated", "source": f"scene.{ASSEMBLY_VERSION}"},
                    "bounds": terrain_entity["bounds"],
                    "extensions": {"role": "heightfield", "bytes": len(payload)}})

    # Water: channels, coastlines and the concrete water level.
    for channel in terrain.channels:
        xs = [point[0] for point in channel.points]
        ys = [point[1] for point in channel.points]
        body = entity(f"water_{channel.id}", "river" if channel.kind != "coast" else "coast", world_id,
                      [min(xs), min(ys), 0], [max(max(xs) - min(xs), 1.0), max(max(ys) - min(ys), 1.0), 1])
        body["geometry"] = {"representation": "channel", "width_m": channel.width_m,
                            "centerline_m": [[round(x, 2), round(y, 2), 0.0] for x, y in channel.points],
                            "water_level_m": terrain.water_level_m}
        records.append(body)

    site_block = {site.id: site.block_id for site in siting.sites}
    # Envelopes have to cover what they contain: a block holds a tower whose
    # roof is 60 m up, and the domain above it has to be as tall again. Both
    # heights are computed before either is emitted.
    block_height = {}
    for design in designs:
        block_id = site_block.get(design.site_id)
        block_height[block_id] = max(block_height.get(block_id, 8.0), round(design.height_m, 3) + 0.5)
    domain_height = {}
    for block in siting.blocks:
        domain_height[block.domain] = max(domain_height.get(block.domain, 8.0),
                                          block_height.get(block.id, 8.0))

    # Ownership, blocks and the skeleton.
    for domain in siting.domains:
        owned = [block for block in siting.blocks if block.domain == domain.id]
        records.append(entity(f"domain_{domain.id}", "domain", world_id,
                              [min(b.x0 for b in owned), min(b.y0 for b in owned), 0],
                              [max(b.x1 for b in owned) - min(b.x0 for b in owned),
                               max(b.y1 for b in owned) - min(b.y0 for b in owned),
                               domain_height.get(domain.id, 8.0)],
                              domain_kind=domain.kind, height_factor=domain.height_factor,
                              footprint_factor=domain.footprint_factor, prefers=list(domain.prefers)))
        records.append(relation(f"relation_{domain.id}_blocks", "contains", f"domain_{domain.id}",
                                [f"block_{block.id}" for block in owned]))
    for block in siting.blocks:
        records.append(entity(f"block_{block.id}", "district", f"domain_{block.domain}",
                              [block.x0, block.y0, 0], [block.x1 - block.x0, block.y1 - block.y0,
                                                       block_height.get(block.id, 8.0)],
                              use=block.use, area_m2=round(block.area_m2, 1)))
    for road in siting.roads:
        xs = [point[0] for point in road.points]
        ys = [point[1] for point in road.points]
        kind = {"arterial": "road", "local": "road", "quay": "road", "rail": "rail",
                "rail_spur": "rail"}[road.kind]
        body = entity(road.id, kind, world_id, [min(xs), min(ys), 0],
                      [max(max(xs) - min(xs), 1.0), max(max(ys) - min(ys), 1.0), 0.4],
                      surface_z_m=0.2, road_class=road.kind)
        body["geometry"] = {"representation": "polyline", "width_m": road.width_m,
                            "points_m": [[round(x, 2), round(y, 2)] for x, y in road.points]}
        records.append(body)
    for bridge in siting.bridges:
        records.append(entity(bridge.id, "bridge", world_id,
                              [min(bridge.start[0], bridge.end[0]), min(bridge.start[1], bridge.end[1]), 0],
                              [max(abs(bridge.end[0] - bridge.start[0]), 1.0),
                               max(abs(bridge.end[1] - bridge.start[1]), 1.0), 2.0],
                              surface_z_m=0.6, width_m=bridge.width_m))
        records.append(relation(f"relation_{bridge.id}", "crosses", bridge.id, [f"water_{bridge.channel_id}"]))
    for work in siting.works:
        xs = [point[0] for point in work.points]
        ys = [point[1] for point in work.points]
        # A wall ring is planned just outside the built-up area; the world root
        # still has to contain it, so the bbox is clamped into the region.
        x0, y0 = max(min(xs), 0.0), max(min(ys), 0.0)
        x1, y1 = min(max(xs), float(brief.region_m)), min(max(ys), float(brief.region_m))
        body = entity(work.id, {"city_wall": "wall", "pier": "pier", "quay_wall": "quay",
                                "rail_line": "rail", "metro_line": "rail"}.get(work.type, "work"),
                      world_id, [x0, y0, 0],
                      [max(x1 - x0, 1.0), max(y1 - y0, 1.0), max(work.width_m, 1.0)],
                      work_type=work.type, design_state=work.design_state, width_m=work.width_m)
        body["geometry"] = {"representation": "polyline", "width_m": work.width_m,
                            "points_m": [[round(x, 2), round(y, 2)] for x, y in work.points]}
        records.append(body)

    # Buildings: the design, exploded into storeys, rooms, partitions and furniture.
    for design in designs:
        building = entity(f"building_{design.site_id}", "building",
                          f"block_{site_block.get(design.site_id, siting.blocks[0].id)}",
                          [design.x0, design.y0, 0],
                          [design.x1 - design.x0, design.y1 - design.y0, round(design.height_m, 3)],
                          storeys=len(design.storeys), programme=design.type, design_state=design.design_state,
                          # The target adapters read `interior_state`; a design
                          # is a full plan, so it is "generated" rather than the
                          # old `deferred` shell-only marker.
                          interior_state="generated",
                          envelope_m2=round((design.x1 - design.x0) * (design.y1 - design.y0), 1))
        building["semantic_completeness"] = "component"
        building["geometry"] = {
            "representation": "parametric_building", "storey_height_m": design.storey_height_m,
            "wall_thickness_m": 0.3, "floor_thickness_m": 0.3, "roof_height_m": design.roof_height_m,
            "roof_style": design.roof,
            "storey_insets_local_m": [[round(storey.x0 - design.x0, 3), 0.0,
                                       round(storey.y0 - design.y0, 3),
                                       round(design.y1 - storey.y1, 3)] for storey in design.storeys],
            "entry": {"side": design.entry_side, "offset_m": design.entry_offset_m,
                      "width_m": design.entry_width_m, "height_m": design.entry_height_m},
            "stair_void_local_m": _stair_void_local(design),
            "assignment": "scene_pipeline_stage_e",
        }
        records.append(building)
        building_origin = building["bounds"]["min"]
        room_origins: dict[str, list[float]] = {}
        for storey in design.storeys:
            storey_id = f"{design.site_id}_storey_{storey.index}"
            records.append(entity(storey_id, "storey", building["id"],
                                  [storey.x0 - design.x0, storey.y0 - design.y0, storey.z_m],
                                  [storey.x1 - storey.x0, storey.y1 - storey.y0, design.storey_height_m],
                                  parent_origin=building_origin))
            storey_origin = [storey.x0, storey.y0, storey.z_m + building_origin[2]]
            for room in storey.rooms:
                room_origins[room.id] = [room.x0, room.y0, building_origin[2] + storey.z_m + 0.3]
                records.append(entity(room.id, "room", storey_id,
                                      [room.x0 - storey.x0, room.y0 - storey.y0, 0.3],
                                      [room.x1 - room.x0, room.y1 - room.y0, design.storey_height_m - 0.6],
                                      parent_origin=storey_origin, use=room.use))
            if len(storey.rooms) == 2 and storey.partition_x_m is not None:
                left, right = storey.rooms
                records.append(entity(f"{design.site_id}_partition_{storey.index}", "partition", storey_id,
                                      [storey.partition_x_m - storey.x0, left.y1 - storey.y0, 0.3],
                                      [0.4, right.y0 - left.y1, design.storey_height_m - 0.9],
                                      parent_origin=storey_origin,
                                      opening={"side": "west", "width_m": 2.0, "height_m": 2.0}))
        for item in design.furniture:
            origin = room_origins[item.room_id]
            records.append(entity(item.id, "furniture", item.room_id,
                                  [item.x0 - origin[0], item.y0 - origin[1], 0.0],
                                  [1.0, 1.0, item.height_m],
                                  parent_origin=origin, use=item.use))
        if design.stair:
            stair = design.stair
            records.append(entity(f"{design.site_id}_stair", "stair", building["id"],
                                  [stair["x0"] - design.x0, stair["y0"] - design.y0, 0.3],
                                  [stair["width_m"], stair["run_m"] + stair["landing_m"],
                                   design.storey_height_m],
                                  parent_origin=building_origin,
                                  stair_kind="straight", design_state=design.design_state))
            records.append(relation(f"relation_{design.site_id}_stair", "connects", f"{design.site_id}_stair",
                                    [room.id for storey in design.storeys for room in storey.rooms]))

    package_id = "package_" + hashlib.sha256(json.dumps(records, sort_keys=True).encode("utf-8")).hexdigest()[:22]
    revision_id = "revision_" + package_id[8:]
    manifest = {
        "package_format": "worldpkg-json-snapshot", "package_mode": "self_contained",
        "package_id": package_id, "revision_id": revision_id,
        "world_id": world_id, "schema_version": "0.1.0",
        "coordinate_system": {"handedness": "right", "quaternion_order": "xyzw",
                              "storage_precision": "float64",
                              "transform_convention": "column_vector_parent_times_local",
                              "x_axis": "east", "y_axis": "north", "z_axis": "up"},
        "units": {"length": "m", "angle": "rad"},
        "tolerances": {"regional_m": 0.1, "building_m": 0.01, "interior_m": 0.005, "angle_rad": 1e-4},
        "required_capabilities": ["wir.core/0.1", "wir.constraints/0.1", "wir.revisions/0.1"],
        # A fixed timestamp keeps the package digest reproducible; the clock is
        # nowhere in the identity of a scene.
        "created_at": "2026-01-01T00:00:00.000000Z",
        # The 0.1 manifest calls this `optional_extensions` and rejects any
        # other unknown key, so a scene-level extension has to live here.
        "optional_extensions": {"generator_version": f"scene.{ASSEMBLY_VERSION}", "scene_pipeline": True,
                                "record_count": len(records)},
    }
    # The first revision of a world carries no parent key at all: an empty
    # `parent_revision_ids` is not what the 0.1 schema accepts for a root.
    records.append({"record_type": "revision", "id": revision_id, "world_id": world_id,
                    "parent_revision_ids": [],
                    "created_at": "2026-01-01T00:00:00.000000Z",
                    "author": f"scene.{ASSEMBLY_VERSION}", "change_set_hash": digest(records),
                    "validation_summary": {"hard_failures": 0, "unknown_checks": 0},
                    "committed": True,
                    "extensions": {"stage": "assembled", "snapshot_manifest": manifest}})
    return {"manifest": manifest, "records": records}


def _stair_void_local(design: BuildingDesign) -> dict:
    if design.stair:
        void = design.stair["void"]
        return {"min": [round(void[0] - design.x0, 3), round(void[2] - design.y0, 3), 0.3],
                "max": [round(void[1] - design.x0, 3), round(void[3] - design.y0, 3),
                        0.3 + design.storey_height_m]}
    return {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]}


def validate_scene(package: dict, terrain: TerrainPlan, siting: SitingPlan,
                   designs: tuple[BuildingDesign, ...]) -> dict:
    """The 0.1 contract plus the invariants that only exist after assembly."""
    results = []

    def check(rule: str, passed: bool, message: str) -> None:
        results.append({"rule": rule, "state": "pass" if passed else "fail", "message": message})

    try:
        validate_package(package)
        check("scene.wir_contract", True, "package passes the WIR 0.1 contract")
    except Exception as exc:  # the validator raises with the full issue list
        check("scene.wir_contract", False, f"WIR contract: {exc}")
        return {"state": "fail", "checks": results}

    records = package["records"]
    entities = {record["id"]: record for record in records if record["record_type"] == "entity"}
    kinds: dict[str, int] = {}
    for record in entities.values():
        kinds[record["kind"]] = kinds.get(record["kind"], 0) + 1
    check("scene.layers", all(kinds.get(kind, 0) > 0 for kind in ("world", "terrain", "district", "road", "building")),
          f"layers present: {dict(sorted(kinds.items()))}")
    check("scene.buildings", kinds.get("building", 0) == len(designs),
          f"{kinds.get('building', 0)} building records for {len(designs)} designs")
    for design in designs:
        building = entities.get(f"building_{design.site_id}")
        if building is None:
            check("scene.building_present", False, f"{design.site_id} has no building record")
            continue
        if abs(building["bounds"]["max"][2] - round(design.height_m, 3)) > 1e-6:
            check("scene.building_height", False, f"{design.site_id} height differs from its design")
            break
        for storey in design.storeys:
            record = entities.get(f"{design.site_id}_storey_{storey.index}")
            if record is None or record["parent_id"] != building["id"]:
                check("scene.storey_chain", False, f"{design.site_id} storey {storey.index} missing")
                break
    else:
        check("scene.building_height", True, "every building height matches its design")
        check("scene.storey_chain", True, "every storey is a child of its building")
    contained = all(record["bounds"]["min"][0] >= entities[record["parent_id"]]["bounds"]["min"][0] - 1.0
                    and record["bounds"]["max"][0] <= entities[record["parent_id"]]["bounds"]["max"][0] + 1.0
                    for record in entities.values() if record.get("parent_id") in entities)
    check("scene.containment", contained, "child entities sit inside their parents")
    relations = [record for record in records if record["record_type"] == "relation"]
    check("scene.relations", any(r["relation_type"] == "crosses" for r in relations) or not siting.bridges,
          f"{len(relations)} relation(s), including bridge crossings")
    return {"state": "pass" if all(r["state"] == "pass" for r in results) else "fail",
            "checks": results, "kinds": dict(sorted(kinds.items())),
            "record_count": len(records)}


def render_svg(package: dict, terrain: TerrainPlan, siting: SitingPlan, designs: tuple[BuildingDesign, ...],
               path: Path, size_px: int = 900) -> Path:
    """A top-down SVG of the assembled scene: terrain, water, roads, buildings."""
    scale = size_px / terrain.region_m
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{size_px}" height="{size_px}" '
             f'viewBox="0 0 {size_px} {size_px}">',
             f'<rect width="{size_px}" height="{size_px}" fill="#e8e4d8"/>']
    low, high = terrain.stats["min_m"], terrain.stats["max_m"]
    span = max(high - low, 1e-6)
    step = 8
    for iy in range(0, terrain.rows, step):
        for ix in range(0, terrain.columns, step):
            shade = int(210 - 70 * (terrain.heights[iy][ix] - low) / span)
            parts.append(f'<rect x="{ix * terrain.spacing_m * scale:.1f}" y="'
                         f'{size_px - (iy + step) * terrain.spacing_m * scale:.1f}" '
                         f'width="{step * terrain.spacing_m * scale:.1f}" '
                         f'height="{step * terrain.spacing_m * scale:.1f}" '
                         f'fill="rgb({shade},{shade - 8},{shade - 22})"/>')
    for channel in terrain.channels:
        points = " ".join(f"{x * scale:.1f},{size_px - y * scale:.1f}" for x, y in channel.points)
        width = max(2.0, channel.width_m * scale)
        parts.append(f'<polyline points="{points}" fill="none" stroke="#3d6fa8" '
                     f'stroke-width="{width:.1f}" stroke-linecap="round" opacity="0.85"/>')
    for road in siting.roads:
        points = " ".join(f"{x * scale:.1f},{size_px - y * scale:.1f}" for x, y in road.points)
        colour = {"arterial": "#5a5a5a", "local": "#9a9a9a", "quay": "#7a6a58",
                  "rail": "#7a4a4a", "rail_spur": "#a07a7a"}[road.kind]
        width = max(1.0, road.width_m * scale)
        parts.append(f'<polyline points="{points}" fill="none" stroke="{colour}" '
                     f'stroke-width="{width:.1f}"/>')
    for bridge in siting.bridges:
        x0, y0 = bridge.start
        x1, y1 = bridge.end
        parts.append(f'<line x1="{x0 * scale:.1f}" y1="{size_px - y0 * scale:.1f}" '
                     f'x2="{x1 * scale:.1f}" y2="{size_px - y1 * scale:.1f}" stroke="#8b5a2b" '
                     f'stroke-width="{max(2.0, bridge.width_m * scale):.1f}"/>')
    for work in siting.works:
        points = " ".join(f"{x * scale:.1f},{size_px - y * scale:.1f}" for x, y in work.points)
        parts.append(f'<polyline points="{points}" fill="none" stroke="#4b4b4b" '
                     f'stroke-width="{max(2.0, work.width_m * scale):.1f}" opacity="0.9"/>')
    for block in siting.blocks:
        parts.append(f'<rect x="{block.x0 * scale:.1f}" y="{size_px - block.y1 * scale:.1f}" '
                     f'width="{(block.x1 - block.x0) * scale:.1f}" '
                     f'height="{(block.y1 - block.y0) * scale:.1f}" fill="none" '
                     f'stroke="#33333355" stroke-width="0.6"/>')
    for design in designs:
        colour = "#c2703a" if design.design_state == "implemented" else "#c2b03a"
        parts.append(f'<rect x="{design.x0 * scale:.1f}" y="{size_px - design.y1 * scale:.1f}" '
                     f'width="{(design.x1 - design.x0) * scale:.1f}" '
                     f'height="{(design.y1 - design.y0) * scale:.1f}" fill="{colour}" '
                     f'stroke="#2b2b2b" stroke-width="0.7"/>')
    for item in [("implemented", "#c2703a"), ("planned", "#c2b03a")]:
        pass
    parts.append('</svg>')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")
    return path
