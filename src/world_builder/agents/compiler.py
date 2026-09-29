"""Compile accepted model-authored cuboids without any local layout policy.

The existing binary serializers, WIR validator and transactional repository are
reused. Neither the historical planner nor any design template is invoked.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import math
from pathlib import Path

from world_builder.adapters.minecraft.city import PALETTE, DEFAULT_DATA_VERSION, voxelize, schematic_bytes
from world_builder.adapters.unity.sample import _glb
from world_builder.storage.repository import Repository
from world_builder.storage.worldpkg import export_worldpkg
from world_builder.wir.validator import validate_package

from .contracts import VERSION, canonical, digest
from .runtime import write_json
from .validation import check_plan, require, tiles_under

BLOCKS = {"stone": "minecraft:stone_bricks", "wood": "minecraft:oak_planks",
          "glass": "minecraft:glass", "brick": "minecraft:bricks", "metal": "minecraft:gray_concrete",
          "grass": "minecraft:grass_block", "white": "minecraft:white_concrete", "water": "minecraft:water"}
COLORS = {"stone": (0.48, 0.48, 0.52, 1), "wood": (0.48, 0.28, 0.14, 1),
          "glass": (0.5, 0.75, 0.9, 0.5), "brick": (0.6, 0.25, 0.18, 1),
          "metal": (0.3, 0.32, 0.34, 1), "grass": (0.25, 0.5, 0.2, 1),
          "white": (0.9, 0.9, 0.87, 1), "water": (0.15, 0.4, 0.8, 0.55)}
STAMP = "2026-01-01T00:00:00.000000Z"


def record_entity(id, kind, parent, bounds, *, parent_origin=(0, 0, 0), material=None, **attributes):
    low, high = bounds["min"], bounds["max"]
    geometry = None if material is None else {"representation": "box", "size_m": [b - a for a, b in zip(low, high)]}
    return {"record_type": "entity", "id": id, "kind": kind, "parent_id": parent,
            "chunk_ids": [f"chunk_{x}_{y}" for x in range(low[0] // 64, math.ceil(high[0] / 64))
                          for y in range(low[1] // 64, math.ceil(high[1] / 64))],
            "transform": {"translation": [low[i] - parent_origin[i] for i in range(3)],
                          "rotation_xyzw": [0, 0, 0, 1], "scale": [1, 1, 1]},
            "bounds": deepcopy(bounds), "generation_state": "materialized",
            "semantic_completeness": "component" if material else "spatial",
            "attributes": {**attributes, **({"agent_material": material} if material else {})},
            "geometry": geometry, "constraint_ids": [], "recipe_id": None, "locks": [],
            "provenance": {"source": "generator", "created_by": f"api-agents.{VERSION}"}, "extensions": {}}


def compile_package(accepted, limits):
    plans, size = accepted["plans"], accepted["region_m"]
    for stage in ("A", "B", "C", "D"):
        check_plan(stage, plans[stage], plans, region_m=size, limits=limits)
    require(set(plans["E"]) == {s["id"] for s in plans["D"]["sites"]}, "scene.coverage", "Incomplete designs")
    for key, design in sorted(plans["E"].items()):
        check_plan("E", design, plans, region_m=size, limits=limits, scope_id=key)
    check_plan("F", plans["F"], plans, region_m=size, limits=limits)
    require(plans["F"]["verdict"] == "accept", "review.pending", "Cannot compile a rejected scene")
    require(sum(len(d["parts"]) for d in plans["E"].values()) <= limits["max_parts"],
            "budget.parts", "Component limit exceeded")
    identity = digest({"accepted": accepted, "compiler_version": VERSION})[7:31]
    world_id, revision_id = "world_" + identity, "revision_" + identity
    region = {"min": [0, 0, 0], "max": [size, size, 80]}
    records = [{"record_type": "world_spec", "id": "spec_agents", "source_prompt": accepted["prompt"],
                "world_seed": f"0x{accepted['seed']:016x}", "region_bounds": region,
                "style_profile": plans["A"]["style"], "target_profile_ids": [], "fantasy_exceptions": [],
                "extensions": {"agent_contract": VERSION, "plans_sha256": digest(plans)}}]
    records.append(record_entity(world_id, "world", None, region))
    terrain = plans["B"]
    step = terrain["cell_m"]
    for row, values in enumerate(terrain["heights"]):
        for col, height in enumerate(values):
            b = {"min": [col * step, row * step, 0], "max": [(col + 1) * step, (row + 1) * step, height]}
            records.append(record_entity(f"terrain_{row}_{col}", "terrain", world_id, b,
                                         material=terrain["ground_material"]))
    for water in terrain["water"]:
        records.append(record_entity("water_" + water["id"], "water", world_id, water["bounds"], material="water"))
    for district in plans["D"]["districts"]:
        x0, y0, x1, y1 = district["rect"]
        records.append(record_entity("district_" + district["id"], "district", world_id,
                                     {"min": [x0, y0, 0], "max": [x1, y1, 80]}, purpose=district["purpose"]))
    for road in plans["D"]["roads"]:
        records.append(record_entity("road_" + road["id"], road["kind"], world_id, road["bounds"], material=road["material"]))
    districts = {d["id"]: d["rect"] for d in plans["D"]["districts"]}
    for site in plans["D"]["sites"]:
        design = plans["E"][site["id"]]
        low, high = site["bounds"]["min"], site["bounds"]["max"]
        building_id = "site_" + site["id"]
        district = districts[site["district_id"]]
        records.append(record_entity(building_id, "building", "district_" + site["district_id"], site["bounds"],
                                     parent_origin=[district[0], district[1], 0],
                                     programme=site["type_id"], concept=design["concept"],
                                     entry_cell_local_m=design["entry_cell"], routes_local_m=design["routes"]))
        if site["foundation"]:
            for col, row, height in tiles_under(site["bounds"], terrain):
                if height < low[2]:
                    b = {"min": [max(low[0], col * step), max(low[1], row * step), height],
                         "max": [min(high[0], (col + 1) * step), min(high[1], (row + 1) * step), low[2]]}
                    # Foundations extend below the building's design envelope;
                    # they belong to the world, with an explicit supporting relation.
                    foundation_id = f"foundation_{site['id']}_{row}_{col}"
                    records.append(record_entity(foundation_id, "foundation", world_id, b, material="stone"))
                    records.append({"record_type": "relation", "id": f"supports_{site['id']}_{row}_{col}",
                                    "relation_type": "supports", "source_id": foundation_id,
                                    "target_ids": [building_id], "attributes": {}, "extensions": {}})
        for item in design["parts"] + design["spaces"]:
            is_part = "material" in item
            b = {key: [item["bounds"][key][i] + low[i] for i in range(3)] for key in ("min", "max")}
            records.append(record_entity(f"{'part' if is_part else 'space'}_{site['id']}_{item['id']}",
                                         item["role"] if is_part else "room", building_id, b, parent_origin=low,
                                         material=item.get("material"),
                                         **({} if is_part else {"programme": item["programme"], "access_cell_local_m": item["access_cell"]})))
    payload = canonical(accepted)
    asset_hash = "sha256:" + hashlib.sha256(payload).hexdigest()
    records.append({"record_type": "asset", "id": "asset_agent_plans", "content_hash": asset_hash,
                    "uri": "assets/sha256/" + asset_hash[7:], "media_type": "application/json",
                    "length_unit": "m", "axis": "RH_Z_up", "bounds": region,
                    "license": {"spdx": "LicenseRef-UserModelOutput", "source": "configured-provider-or-fixture"}})
    manifest = {"package_format": "worldpkg-json-snapshot", "schema_version": "0.1.0",
                "package_id": "package_" + identity, "world_id": world_id, "revision_id": revision_id,
                "required_capabilities": ["wir.core/0.1", "wir.constraints/0.1", "wir.revisions/0.1"],
                "units": {"length": "m", "angle": "rad"},
                "coordinate_system": {"handedness": "right", "x_axis": "east", "y_axis": "north", "z_axis": "up",
                                      "transform_convention": "column_vector_parent_times_local",
                                      "quaternion_order": "xyzw", "storage_precision": "float64"},
                "tolerances": {"regional_m": 0.1, "building_m": 0.01, "interior_m": 0.005, "angle_rad": 0.0001},
                "package_mode": "self_contained", "created_at": STAMP,
                "optional_extensions": {"api_agents_version": VERSION, "geometry": "integer_cuboids_v1"}}
    records.append({"record_type": "revision", "id": revision_id, "world_id": world_id,
                    "parent_revision_ids": [], "created_at": STAMP, "author": "api-agents",
                    "change_set_hash": digest(records), "validation_summary": {"hard_failures": 0, "unknown_checks": 0},
                    "committed": True, "extensions": {"snapshot_manifest": manifest}})
    package = {"manifest": manifest, "records": records}
    validate_package(package)
    return package, payload


def export_geometry(package, output, limits, *, minecraft=False, unity=False):
    validate_package(package)
    require(package["manifest"].get("optional_extensions", {}).get("api_agents_version") == VERSION,
            "export.version", "Not a supported agent package")
    root = Path(output)
    parts = [r for r in package["records"] if r["record_type"] == "entity" and r["geometry"] is not None]
    require(bool(parts), "export.empty", "Package has no components")
    volume = sum(math.prod(b - a for a, b in zip(p["bounds"]["min"], p["bounds"]["max"])) for p in parts)
    require(volume <= limits["max_voxels"], "budget.voxels", "Authored volume exceeds compilation budget")
    material_names = list(BLOCKS)
    pieces = [{"name": p["id"], "source_id": p["id"], "bounds_wir_m": [p["bounds"]["min"], p["bounds"]["max"]],
               "material": material_names.index(p["attributes"]["agent_material"])} for p in parts]
    result = {}
    if unity:
        directory = root / "unity"
        directory.mkdir(parents=True, exist_ok=False)
        glb = _glb(pieces, [(name, COLORS[name]) for name in material_names])
        (directory / "scene.glb").write_bytes(glb)
        write_json(directory / "manifest.json", {"version": VERSION, "source_revision_id": package["manifest"]["revision_id"],
                   "glb_sha256": "sha256:" + hashlib.sha256(glb).hexdigest(), "parts": pieces,
                   "coordinate_system": "glTF RH Y-up: WIR (x,y,z) -> (-x,z,y); glTFast reflects X for Unity",
                   "colliders": "consumer_must_add_per_solid_mesh; water_not_solid", "target_load": "not_run"})
        result["unity"] = {"mesh_count": len(pieces), "sha256": "sha256:" + hashlib.sha256(glb).hexdigest()}
        write_export_report(package, directory, "unity", parts)
    if minecraft:
        boxes = []
        for p in parts:
            lo, hi = p["bounds"]["min"], p["bounds"]["max"]
            boxes.append({"source_id": p["id"], "x0": lo[0], "x1": hi[0], "y0": lo[2], "y1": hi[2],
                          "z0": -hi[1], "z1": -lo[1], "block": BLOCKS[p["attributes"]["agent_material"]]})
        y0, y1 = 0, max(b["y1"] for b in boxes)
        chunk_keys = {(x, z) for b in boxes for x in range(b["x0"] // 128, math.ceil(b["x1"] / 128))
                      for z in range(b["z0"] // 128, math.ceil(b["z1"] / 128))}
        require(len(chunk_keys) * 128 * 128 * (y1 - y0) <= limits["max_voxels"],
                "budget.voxel_memory", "Padded schematic allocation exceeds voxel budget")
        chunks = voxelize(boxes, y0, y1)
        directory = root / "minecraft"
        directory.mkdir(parents=True, exist_ok=False)
        index = []
        for (cx, cz), grid in sorted(chunks.items()):
            blob = schematic_bytes(grid, DEFAULT_DATA_VERSION, y1 - y0)
            name = f"agent_{cx}_{cz}.schem"
            (directory / name).write_bytes(blob)
            index.append({"path": name, "chunk_x": cx, "chunk_z": cz,
                          "world_min": [cx * 128, y0, cz * 128], "world_max_exclusive": [(cx + 1) * 128, y1, (cz + 1) * 128],
                          "sha256": "sha256:" + hashlib.sha256(blob).hexdigest(),
                          "non_air_blocks": sum(bool(v) for v in grid)})
        write_json(directory / "manifest.json", {"version": VERSION, "format": "sponge-schematic-v3",
                   "data_version": DEFAULT_DATA_VERSION, "source_revision_id": package["manifest"]["revision_id"],
                   "palette": PALETTE, "chunks": index, "meters_per_block": 1,
                   "coordinate_system": "WIR (x,y,z) -> Minecraft (x,z,-y)",
                   "requires_clear_before_paste": True, "target_load": "not_run", "walkthrough": "not_run"})
        result["minecraft"] = {"chunks": len(index), "blocks": sum(c["non_air_blocks"] for c in index)}
        write_export_report(package, directory, "minecraft_java", parts)
    return result


def write_export_report(package, directory, target, parts):
    represented = {p["id"] for p in parts}
    profile_id = "profile_agents_" + target
    items = []
    for record in package["records"]:
        if record["record_type"] != "entity":
            continue
        visible = record["id"] in represented
        items.append({"source_id": record["id"], "target_id": record["id"] if visible else None,
                      "classification": "approximated" if visible else "omitted",
                      "message": ("Authored integer cuboid preserved spatially; material/lighting/physics are target approximations"
                                  if visible else "Semantic container or clear space retained in source WIR, not a solid mesh/block")})
    profile = {"record_type": "target_profile", "id": profile_id, "target": target,
               "target_version": "1.21.11" if target == "minecraft_java" else "6000.3.24f1",
               "adapter_version": "api-agents." + VERSION,
               "configuration": {"units": "m", "geometry": "integer_cuboids_v1"},
               "declared_capabilities": ["explicit_cuboids", "source_ids", "static_scene"], "extensions": {}}
    report = {"record_type": "export_report", "id": "report_agents_" + target,
              "revision_id": package["manifest"]["revision_id"], "target_profile_id": profile_id,
              "status": "succeeded_with_warnings",
              # Unity's matrix describes the target engine after glTFast's reflection.
              "coordinate_transform_row_major": [1,0,0,0, 0,0,1,0, 0,(-1 if target == "minecraft_java" else 1),0,0, 0,0,0,1],
              "items": items, "summary": {key: sum(i["classification"] == key for i in items)
                   for key in ("preserved", "approximated", "omitted", "unsupported", "failed")},
              "extensions": {"target_load": "not_run", "walkthrough": "not_run",
                             "route_check": "source_discrete_one_block_jump",
                             "limitations": ["No lighting, structure, water or engine collision simulation",
                                             "Unity consumer must add colliders; voxel jump routes are not CharacterController proof"]}}
    derived = deepcopy(package)
    derived["records"].extend([profile, report])
    next(r for r in derived["records"] if r["record_type"] == "world_spec")["target_profile_ids"].append(profile_id)
    validate_package(derived)
    write_json(directory / "export_report.json", report)
    write_json(directory / "target_profile.json", profile)


def save_world(accepted, output, limits, *, minecraft=False, unity=False):
    package, payload = compile_package(accepted, limits)
    root = Path(output)
    # Export validation and capacity checks precede the authoritative commit.
    exports = export_geometry(package, root, limits, minecraft=minecraft, unity=unity)
    repository = Repository(root / "repository")
    checksum, _ = repository.publish(payload)
    require(checksum == digest(accepted), "asset.hash", "Published plan hash mismatch")
    repository.commit(package, None)
    archive_hash = export_worldpkg(repository, package["manifest"]["world_id"], root / "scene.worldpkg")
    # Put the standalone JSON beside its content-addressed assets.
    write_json(repository.root / "scene.world.json", package)
    result = {"world_id": package["manifest"]["world_id"], "revision_id": package["manifest"]["revision_id"],
              "worldpkg_sha256": archive_hash, "exports": exports,
              "source_geometry_validation": "pass", "target_load": "not_run", "walkthrough": "not_run"}
    write_json(root / "result.json", result)
    return result
