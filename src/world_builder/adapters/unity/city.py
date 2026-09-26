"""Bounded, source-derived static Unity city export for WIR city snapshots.

The output is a collision-ready ordinary GLB mesh. Terrain and parametric
buildings are explicit proxies; this adapter does not claim interior fidelity.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

from world_builder.adapters.unity.sample import (_box, _canonical, _glb,
                                                GLTFAST_VERSION, UNITY_VERSION,
                                                URP_VERSION)
from world_builder.wir.validator import validate_package

ADAPTER_VERSION = "0.1.0-city.1"
PROFILE_ID = "profile_unity_city_6000324"
INTERIOR_ADAPTER_VERSION = "0.1.0-city.2"
INTERIOR_PROFILE_ID = "profile_unity_city_6000324_v2"
CHUNKED_ADAPTER_VERSION = "0.1.0-city.3"
CHUNKED_PROFILE_ID = "profile_unity_city_6000324_v3"
CHUNK_SIZE_M = 128
EXPORT_KINDS = {"road", "bridge", "building", "wall"}


class CityExportError(ValueError):
    pass


def _chunk_pieces(pieces: list[dict], origin_x: float, origin_n: float) -> dict[str, list[dict]]:
    """Clip every box to a half-open 128 m horizontal grid; retain source IDs."""
    chunks: dict[str, list[dict]] = {}
    for piece in pieces:
        (x0, n0, u0), (x1, n1, u1) = piece["bounds_wir_m"]
        first_x = math.floor((x0 - origin_x) / CHUNK_SIZE_M)
        last_x = math.floor((math.nextafter(x1, -math.inf) - origin_x) / CHUNK_SIZE_M)
        first_n = math.floor((n0 - origin_n) / CHUNK_SIZE_M)
        last_n = math.floor((math.nextafter(n1, -math.inf) - origin_n) / CHUNK_SIZE_M)
        for ix in range(first_x, last_x + 1):
            for iz in range(first_n, last_n + 1):
                cx0, cn0 = origin_x + ix * CHUNK_SIZE_M, origin_n + iz * CHUNK_SIZE_M
                clipped = _box(f"{piece['name']}__c{ix:02}_{iz:02}", piece["source_id"],
                               max(x0, cx0), min(x1, cx0 + CHUNK_SIZE_M),
                               max(n0, cn0), min(n1, cn0 + CHUNK_SIZE_M),
                               u0, u1, piece["material"])
                chunk_id = f"c{ix:02}_{iz:02}"
                clipped["chunk_id"] = chunk_id
                chunks.setdefault(chunk_id, []).append(clipped)
    return dict(sorted(chunks.items()))


def _interior_pieces(building: dict, entities: dict[str, dict]) -> list[dict]:
    """Apply a versioned shell/stair policy to a source-generated two-storey plan."""
    children = [r for r in entities.values() if r["parent_id"] == building["id"]]
    storeys = sorted((r for r in children if r["kind"] == "storey"), key=lambda r: r["bounds"]["min"][2])
    stairs = [r for r in children if r["kind"] == "stair"]
    if len(storeys) != 2 or len(stairs) != 1:
        raise CityExportError("interior building requires two storeys and one stair: " + building["id"])
    stair = stairs[0]
    g, sg = building["geometry"], stair["geometry"]
    if (g["representation"] != "parametric_building" or g["entry"]["side"] != "east"
            or sg["representation"] != "straight_stair" or sg["steps"] < 1):
        raise CityExportError("unsupported interior geometry: " + building["id"])
    (x0, n0, z0), (x1, n1, z1) = building["bounds"]["min"], building["bounds"]["max"]
    wall, floor = g["wall_thickness_m"], g["floor_thickness_m"]
    upper_z = storeys[1]["bounds"]["min"][2]
    upper_top = upper_z + floor
    void = g["stair_void_local_m"]
    vx0, vn0 = x0 + void["min"][0], n0 + void["min"][1]
    vx1, vn1 = x0 + void["max"][0], n0 + void["max"][1]
    (sx0, sn0, _), (sx1, sn1, _) = stair["bounds"]["min"], stair["bounds"]["max"]
    if not (x0 < vx0 < vx1 < x1 and n0 < vn0 < vn1 < n1
            and vx0 <= sx0 < sx1 <= vx1 and vn0 <= sn0 < sn1 <= vn1
            and abs(sg["floor_levels_m"][0] - (z0 + floor)) < 0.01
            and abs(sg["floor_levels_m"][1] - upper_top) < 0.01):
        raise CityExportError("stair void or levels do not match source plan: " + building["id"])
    entry = g["entry"]
    door_n0, door_n1 = n0 + entry["offset_m"], n0 + entry["offset_m"] + entry["width_m"]
    door_top = z0 + floor + entry["height_m"]
    if not (n0 + wall < door_n0 < door_n1 < n1 - wall and door_top < z1 - g["roof_height_m"]):
        raise CityExportError("entry opening does not fit shell: " + building["id"])
    name = building["id"]
    parts = [
        _box(name + "_ground_floor", storeys[0]["id"], x0, x1, n0, n1, z0, z0 + floor, 1),
        _box(name + "_west_wall", name, x0, x0 + wall, n0, n1, z0 + floor, z1 - g["roof_height_m"], 0),
        _box(name + "_south_wall", name, x0 + wall, x1 - wall, n0, n0 + wall, z0 + floor, z1 - g["roof_height_m"], 0),
        _box(name + "_north_wall", name, x0 + wall, x1 - wall, n1 - wall, n1, z0 + floor, z1 - g["roof_height_m"], 0),
        _box(name + "_east_wall_south", name, x1 - wall, x1, n0 + wall, door_n0, z0 + floor, z1 - g["roof_height_m"], 0),
        _box(name + "_east_wall_north", name, x1 - wall, x1, door_n1, n1 - wall, z0 + floor, z1 - g["roof_height_m"], 0),
        _box(name + "_east_door_lintel", name, x1 - wall, x1, door_n0, door_n1, door_top, z1 - g["roof_height_m"], 0),
        _box(name + "_upper_floor_west", storeys[1]["id"], x0, vx0, n0, n1, upper_z, upper_top, 1),
        _box(name + "_upper_floor_east", storeys[1]["id"], vx1, x1, n0, n1, upper_z, upper_top, 1),
        _box(name + "_upper_floor_south", storeys[1]["id"], vx0, vx1, n0, vn0, upper_z, upper_top, 1),
        _box(name + "_upper_floor_north", storeys[1]["id"], vx0, vx1, vn1, n1, upper_z, upper_top, 1),
        _box(name + "_flat_roof_proxy", name, x0, x1, n0, n1, z1 - g["roof_height_m"], z1, 1),
    ]
    step_run, step_rise = sg["run_m"] / sg["steps"], sg["rise_m"] / sg["steps"]
    clear_x0 = sx0 + (sx1 - sx0 - sg["clear_width_m"]) / 2
    for index in range(sg["steps"]):
        parts.append(_box(f"{stair['id']}_tread_{index + 1:02}", stair["id"],
                          clear_x0, clear_x0 + sg["clear_width_m"],
                          sn0 + index * step_run, sn0 + (index + 1) * step_run,
                          z0 + floor, z0 + floor + (index + 1) * step_rise, 3))
    parts.append(_box(stair["id"] + "_landing", stair["id"], clear_x0,
                      clear_x0 + sg["clear_width_m"], sn0 + sg["run_m"], sn1,
                      upper_z, upper_top, 3))
    for item in sorted((r for r in entities.values() if r["kind"] == "furniture"
                        and r["parent_id"] in {r["id"] for r in entities.values()
                                               if r["kind"] == "room" and r["parent_id"] in {s["id"] for s in storeys}}),
                       key=lambda r: r["id"]):
        low, high = item["bounds"]["min"], item["bounds"]["max"]
        parts.append(_box(item["id"] + "_proxy", item["id"], low[0], high[0], low[1], high[1], low[2], high[2], 3))
    return parts


def export_city(package: dict, output_dir: str | Path, *, include_interiors: bool = False,
                chunked: bool = False) -> dict:
    if chunked and not include_interiors:
        raise CityExportError("chunked v3 requires include_interiors=True")
    validate_package(package)
    specs = [r for r in package["records"] if r["record_type"] == "world_spec"]
    if len(specs) != 1 or "city_spec" not in specs[0].get("extensions", {}):
        raise CityExportError("a WIR city_spec snapshot is required")
    if package["manifest"]["coordinate_system"]["x_axis"] != "east" or package["manifest"]["coordinate_system"]["y_axis"] != "north":
        raise CityExportError("unsupported source axes")
    entities = sorted((r for r in package["records"] if r["record_type"] == "entity"), key=lambda r: r["id"])
    by_id = {r["id"]: r for r in entities}
    kinds = {r["kind"] for r in entities}
    if not {"terrain", "river", "road", "bridge", "building"} <= kinds:
        raise CityExportError("city is missing required spatial layers")
    pieces = []
    for record in entities:
        if record["kind"] not in EXPORT_KINDS:
            continue
        if record["geometry"]["representation"] not in {"box", "parametric_building"}:
            raise CityExportError("unsupported source geometry: " + record["id"])
        if (include_interiors and record["kind"] == "building"
                and record["attributes"]["interior_state"] == "generated"):
            pieces.extend(_interior_pieces(record, by_id))
            continue
        low, high = record["bounds"]["min"], record["bounds"]["max"]
        pieces.append(_box(record["id"], record["id"], low[0], high[0], low[1], high[1],
                           low[2], high[2], {"road": 0, "bridge": 3, "building": 1, "wall": 0}[record["kind"]]))
    terrain = next(r for r in entities if r["kind"] == "terrain")
    river = next(r for r in entities if r["kind"] == "river")
    tlo, thi = terrain["bounds"]["min"], terrain["bounds"]["max"]
    rlo, rhi = river["bounds"]["min"], river["bounds"]["max"]
    if not (tlo[0] < rlo[0] < rhi[0] < thi[0] and tlo[1] == rlo[1] and thi[1] == rhi[1]):
        raise CityExportError("terrain proxy requires a straight north-south river")
    pieces.extend([
        _box("terrain_west_proxy", terrain["id"], tlo[0], rlo[0], tlo[1], thi[1], -0.2, 0.25, 0),
        _box("terrain_east_proxy", terrain["id"], rhi[0], thi[0], tlo[1], thi[1], -0.2, 0.25, 0),
        _box("river_water_proxy", river["id"], rlo[0], rhi[0], rlo[1], rhi[1], -0.05, 0.05, 2),
    ])
    chunks = _chunk_pieces(pieces, tlo[0], tlo[1]) if chunked else None
    if chunks is not None:
        pieces = [piece for group in chunks.values() for piece in group]
    else:
        glb = _glb(pieces)
    source_hash = "sha256:" + hashlib.sha256(json.dumps(package, ensure_ascii=False, sort_keys=True,
                                                         separators=(",", ":")).encode()).hexdigest()
    represented = {piece["source_id"] for piece in pieces}
    adapter_version = (CHUNKED_ADAPTER_VERSION if chunked else
                       INTERIOR_ADAPTER_VERSION if include_interiors else ADAPTER_VERSION)
    profile_id = (CHUNKED_PROFILE_ID if chunked else
                  INTERIOR_PROFILE_ID if include_interiors else PROFILE_ID)
    items = []
    for record in entities:
        kind = record["kind"]
        if kind == "world":
            classification, target, message = "preserved", "scene:" + record["id"], "world identity retained in scene and sidecar"
        elif kind in {"road", "bridge", "wall"}:
            classification, target, message = "preserved", "glb:" + record["id"], "axis-aligned box mesh and collider; source bounds retained"
        elif kind == "building":
            if include_interiors and record["attributes"]["interior_state"] == "generated":
                classification, target, message = "approximated", "glb:" + record["id"] + "_*", "source entrance, floor and stair parameters drive adapter-policy shell; roof is flat proxy"
            else:
                classification, target, message = "approximated", "glb:" + record["id"], "solid bounds proxy; entry, roof, storeys and interior are not modeled"
        elif kind == "terrain":
            classification, target, message = "approximated", "glb:terrain_*_proxy", "flat banks replace source heightfield; no native Unity Terrain"
        elif kind == "river":
            classification, target, message = "approximated", "glb:river_water_proxy", "straight translucent water box; no fluid simulation"
        elif include_interiors and record["id"] in represented:
            classification, target, message = "approximated", "glb:" + record["id"] + "_*", "source floor, stair or furniture bounds materialized using adapter geometry policy"
        else:
            classification, target, message = "omitted", None, "source entity retained in WIR package but not represented in this static GLB"
        items.append({"source_id": record["id"], "target_id": target,
                      "classification": classification, "message": message})
    summary = {key: sum(item["classification"] == key for item in items)
               for key in ("preserved", "approximated", "omitted", "unsupported", "failed")}
    report_id = "report_unity_city_v3" if chunked else "report_unity_city_v2" if include_interiors else "report_unity_city"
    report = {"record_type": "export_report", "id": report_id,
              "revision_id": package["manifest"]["revision_id"], "target_profile_id": profile_id,
              "status": "succeeded_with_warnings", "coordinate_transform_row_major":
              [1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1],
              "items": items, "summary": summary,
              "extensions": {"adapter_version": adapter_version, "target_load": "not_run",
                             "collision": "not_run", "walkthrough": "not_run"}}
    profile = {"record_type": "target_profile", "id": profile_id, "target": "unity",
               "target_version": UNITY_VERSION + "+urp-" + URP_VERSION + "+gltfast-" + GLTFAST_VERSION,
               "adapter_version": adapter_version,
               "configuration": {"meters_per_unit": 1, "x_axis": "east", "y_axis": "up",
                                 "z_axis": "north", "mesh_format": "glb-2.0", "terrain": "ordinary_mesh",
                                 **({"chunk_size_m": CHUNK_SIZE_M} if chunked else {})},
               "declared_capabilities": ["mesh", "materials", "mesh_collider"], "extensions": {}}
    derived = copy.deepcopy(package)
    derived["records"].extend([profile, report])
    next(r for r in derived["records"] if r["record_type"] == "world_spec")["target_profile_ids"].append(profile_id)
    validate_package(derived)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    chunk_files = {}
    chunk_index = []
    if chunks is not None:
        for chunk_id, group in chunks.items():
            path = f"chunks/city_{chunk_id}.glb"
            data = _glb(group)
            chunk_files[path] = data
            chunk_index.append({"id": chunk_id, "path": path, "glb_sha256":
                                "sha256:" + hashlib.sha256(data).hexdigest(),
                                "piece_count": len(group)})
    manifest = {
        "format": "unity-glb-city-0.3" if chunked else "unity-glb-city-0.2" if include_interiors else "unity-glb-city-0.1", "source_world_id": package["manifest"]["world_id"],
        "source_revision_id": package["manifest"]["revision_id"], "source_snapshot_hash": source_hash,
        "adapter_version": adapter_version, "target_profile_id": profile_id,
        "unity_version": UNITY_VERSION, "urp_version": URP_VERSION, "gltfast_version": GLTFAST_VERSION,
        **({"chunks": chunk_index, "chunk_size_m": CHUNK_SIZE_M,
            "chunk_origin_wir_m": [tlo[0], tlo[1]]} if chunked else
           {"glb_sha256": "sha256:" + hashlib.sha256(glb).hexdigest()}),
        "pieces": pieces,
        "source_to_glb_row_major": [-1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1],
        "source_to_unity_row_major": report["coordinate_transform_row_major"],
        "target_load": "not_run", "collision": "not_run", "walkthrough": "not_run"}
    files = {"manifest.json": _canonical(manifest),
             "export_report.json": _canonical(report), "target_profile.json": _canonical(profile),
             **(chunk_files if chunked else {"city.glb": glb})}
    for name, data in files.items():
        (output / name).parent.mkdir(parents=True, exist_ok=True)
        (output / name).write_bytes(data)
    result = {"output": str(output), "source_revision_id": package["manifest"]["revision_id"],
              "piece_count": len(pieces), "report_summary": summary}
    result.update({"chunk_count": len(chunks)} if chunked else
                  {"glb_sha256": hashlib.sha256(glb).hexdigest()})
    return result
