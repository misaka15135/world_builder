"""Bounded, source-derived static Unity city export for WIR city snapshots.

The output is a collision-ready ordinary GLB mesh. Terrain and parametric
buildings are explicit proxies; this adapter does not claim interior fidelity.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from world_builder.adapters.unity.sample import (_box, _canonical, _glb,
                                                GLTFAST_VERSION, UNITY_VERSION,
                                                URP_VERSION)
from world_builder.wir.validator import validate_package

ADAPTER_VERSION = "0.1.0-city.1"
PROFILE_ID = "profile_unity_city_6000324"
EXPORT_KINDS = {"road", "bridge", "building"}


class CityExportError(ValueError):
    pass


def export_city(package: dict, output_dir: str | Path) -> dict:
    validate_package(package)
    specs = [r for r in package["records"] if r["record_type"] == "world_spec"]
    if len(specs) != 1 or "city_spec" not in specs[0].get("extensions", {}):
        raise CityExportError("a WIR city_spec snapshot is required")
    if package["manifest"]["coordinate_system"]["x_axis"] != "east" or package["manifest"]["coordinate_system"]["y_axis"] != "north":
        raise CityExportError("unsupported source axes")
    entities = sorted((r for r in package["records"] if r["record_type"] == "entity"), key=lambda r: r["id"])
    kinds = {r["kind"] for r in entities}
    if not {"terrain", "river", "road", "bridge", "building"} <= kinds:
        raise CityExportError("city is missing required spatial layers")
    pieces = []
    for record in entities:
        if record["kind"] not in EXPORT_KINDS:
            continue
        if record["geometry"]["representation"] not in {"box", "parametric_building"}:
            raise CityExportError("unsupported source geometry: " + record["id"])
        low, high = record["bounds"]["min"], record["bounds"]["max"]
        pieces.append(_box(record["id"], record["id"], low[0], high[0], low[1], high[1],
                           low[2], high[2], {"road": 0, "bridge": 3, "building": 1}[record["kind"]]))
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
    glb = _glb(pieces)
    source_hash = "sha256:" + hashlib.sha256(json.dumps(package, ensure_ascii=False, sort_keys=True,
                                                         separators=(",", ":")).encode()).hexdigest()
    items = []
    for record in entities:
        kind = record["kind"]
        if kind == "world":
            classification, target, message = "preserved", "scene:" + record["id"], "world identity retained in scene and sidecar"
        elif kind in {"road", "bridge"}:
            classification, target, message = "preserved", "glb:" + record["id"], "axis-aligned box mesh and collider; source bounds retained"
        elif kind == "building":
            classification, target, message = "approximated", "glb:" + record["id"], "solid bounds proxy; entry, roof, storeys and interior are not modeled"
        elif kind == "terrain":
            classification, target, message = "approximated", "glb:terrain_*_proxy", "flat banks replace source heightfield; no native Unity Terrain"
        elif kind == "river":
            classification, target, message = "approximated", "glb:river_water_proxy", "straight translucent water box; no fluid simulation"
        else:
            classification, target, message = "omitted", None, "source entity retained in WIR package but not represented in this static GLB"
        items.append({"source_id": record["id"], "target_id": target,
                      "classification": classification, "message": message})
    summary = {key: sum(item["classification"] == key for item in items)
               for key in ("preserved", "approximated", "omitted", "unsupported", "failed")}
    report = {"record_type": "export_report", "id": "report_unity_city",
              "revision_id": package["manifest"]["revision_id"], "target_profile_id": PROFILE_ID,
              "status": "succeeded_with_warnings", "coordinate_transform_row_major":
              [1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1],
              "items": items, "summary": summary,
              "extensions": {"adapter_version": ADAPTER_VERSION, "target_load": "not_run",
                             "collision": "not_run", "walkthrough": "not_run"}}
    profile = {"record_type": "target_profile", "id": PROFILE_ID, "target": "unity",
               "target_version": UNITY_VERSION + "+urp-" + URP_VERSION + "+gltfast-" + GLTFAST_VERSION,
               "adapter_version": ADAPTER_VERSION,
               "configuration": {"meters_per_unit": 1, "x_axis": "east", "y_axis": "up",
                                 "z_axis": "north", "mesh_format": "glb-2.0", "terrain": "ordinary_mesh"},
               "declared_capabilities": ["mesh", "materials", "mesh_collider"], "extensions": {}}
    derived = copy.deepcopy(package)
    derived["records"].extend([profile, report])
    next(r for r in derived["records"] if r["record_type"] == "world_spec")["target_profile_ids"].append(PROFILE_ID)
    validate_package(derived)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    files = {"city.glb": glb, "manifest.json": _canonical({
        "format": "unity-glb-city-0.1", "source_world_id": package["manifest"]["world_id"],
        "source_revision_id": package["manifest"]["revision_id"], "source_snapshot_hash": source_hash,
        "adapter_version": ADAPTER_VERSION, "target_profile_id": PROFILE_ID,
        "unity_version": UNITY_VERSION, "urp_version": URP_VERSION, "gltfast_version": GLTFAST_VERSION,
        "glb_sha256": "sha256:" + hashlib.sha256(glb).hexdigest(), "pieces": pieces,
        "source_to_glb_row_major": [-1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1],
        "source_to_unity_row_major": report["coordinate_transform_row_major"],
        "target_load": "not_run", "collision": "not_run", "walkthrough": "not_run"}),
             "export_report.json": _canonical(report), "target_profile.json": _canonical(profile)}
    for name, data in files.items():
        (output / name).write_bytes(data)
    return {"output": str(output), "source_revision_id": package["manifest"]["revision_id"],
            "piece_count": len(pieces), "report_summary": summary,
            "glb_sha256": hashlib.sha256(glb).hexdigest()}
