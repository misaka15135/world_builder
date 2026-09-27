"""Narrow, deterministic GLB experiment for the frozen two-storey WIR sample.

The source only specifies building/room/stair volumes. Walls, openings, treads,
and the chair proxy below are explicit adapter policy, not inferred source facts.
"""
from __future__ import annotations

import copy
import hashlib
import json
import struct
from pathlib import Path

from world_builder.wir.validator import validate_package

ADAPTER_VERSION = "0.1.0-sample.1"
SOURCE_HASH = "sha256:07afdf589fc3ddb045d27af0dadabafa58f8b6cea010405bec24b2db62e4f8bb"
UNITY_VERSION = "6000.3.24f1"
URP_VERSION = "17.3.0"
GLTFAST_VERSION = "6.20.0"


class SampleExportError(ValueError):
    pass


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _box(name: str, source_id: str, x0: float, x1: float, north0: float, north1: float,
         up0: float, up1: float, material: int) -> dict:
    if not (x0 < x1 and north0 < north1 and up0 < up1):
        raise SampleExportError(f"invalid box: {name}")
    return {"name": name, "source_id": source_id,
            "bounds_wir_m": [[x0, north0, up0], [x1, north1, up1]], "material": material}


def _pieces() -> list[dict]:
    b = "building_arcane_library"
    s = "stair_library_main"
    parts = [
        _box("foundation", b, 4, 24, 3, 19, -0.2, 0, 0),
        _box("ground_floor", b, 4, 24, 3, 19, 0, 0.2, 1),
        _box("south_wall_left", b, 4, 13, 3, 3.25, 0.2, 8, 0),
        _box("south_wall_right", b, 15, 24, 3, 3.25, 0.2, 8, 0),
        _box("south_door_lintel", b, 13, 15, 3, 3.25, 2.5, 8, 0),
        _box("north_wall", b, 4, 24, 18.75, 19, 0.2, 8, 0),
        _box("west_wall", b, 4, 4.25, 3.25, 18.75, 0.2, 8, 0),
        _box("east_wall_south", b, 23.75, 24, 3.25, 12, 0.2, 8, 0),
        _box("east_wall_north", b, 23.75, 24, 14, 18.75, 0.2, 8, 0),
        _box("east_window_sill", b, 23.75, 24, 12, 14, 0.2, 5, 0),
        _box("east_window_header", b, 23.75, 24, 12, 14, 7, 8, 0),
        _box("east_bay_glass", b, 23.75, 24, 12, 14, 5, 7, 2),
        _box("upper_floor_west", b, 4, 16, 3.25, 18.75, 4, 4.2, 1),
        _box("upper_floor_east_south", b, 16, 23.75, 3.25, 8, 4, 4.2, 1),
        _box("upper_floor_east_north", b, 16, 23.75, 12, 18.75, 4, 4.2, 1),
        _box("upper_floor_east_edge", b, 18, 23.75, 8, 12, 4, 4.2, 1),
        _box("roof", b, 4, 24, 3, 19, 8, 8.25, 1),
    ]
    for index in range(8):
        parts.append(_box(f"stair_tread_{index + 1:02}", s, 16.3, 17.7,
                          8 + index * 0.5, 8.5 + index * 0.5,
                          0.2, 0.5 * (index + 1), 3))
    parts.append(_box("chair_proxy", "chair_reading_001", 9.7, 10.3, 8.7, 9.3, 0.2, 1.1, 3))
    return parts


def _glb(pieces: list[dict], materials: list[tuple[str, tuple[float, float, float, float]]] | None = None) -> bytes:
    """Write GLB 2.0 with one indexed, flat-shaded cuboid mesh per part.

    glTF uses RH Y-up: WIR (east,north,up) -> (west,up,north).
    glTFast 6.20.0 reflects the glTF X axis on import, so Unity receives
    (east,up,north). This is verified against an asymmetric bay window.
    """
    materials = materials or [
        ("stone", (0.48, 0.48, 0.52, 1)), ("oak", (0.47, 0.27, 0.13, 1)),
        ("glass", (0.54, 0.77, 0.86, 0.6)), ("dark_oak", (0.31, 0.17, 0.08, 1))]
    doc = {"asset": {"version": "2.0", "generator": "world_builder unity sample 0.1"},
           "scene": 0, "scenes": [{"nodes": list(range(len(pieces)))}],
           "nodes": [], "meshes": [], "materials": [], "accessors": [], "bufferViews": [], "buffers": []}
    for i, (name, color) in enumerate(materials):
        pbr = {"baseColorFactor": color, "metallicFactor": 0, "roughnessFactor": 0.9}
        mat = {"name": name,
               "pbrMetallicRoughness": pbr, "doubleSided": False}
        if color[3] < 1:
            mat["alphaMode"] = "BLEND"
        doc["materials"].append(mat)
    binary = bytearray()

    def add_view(data: bytes, target: int) -> int:
        while len(binary) % 4:
            binary.append(0)
        offset = len(binary)
        binary.extend(data)
        doc["bufferViews"].append({"buffer": 0, "byteOffset": offset,
                                   "byteLength": len(data), "target": target})
        return len(doc["bufferViews"]) - 1

    def add_accessor(view: int, component: int, count: int, kind: str,
                     low: list[float] | None = None, high: list[float] | None = None) -> int:
        acc = {"bufferView": view, "componentType": component, "count": count, "type": kind}
        if low is not None:
            acc["min"], acc["max"] = low, high
        doc["accessors"].append(acc)
        return len(doc["accessors"]) - 1

    faces = [((4, 5, 6, 7), (0, 0, 1)), ((1, 0, 3, 2), (0, 0, -1)),
             ((5, 1, 2, 6), (1, 0, 0)), ((0, 4, 7, 3), (-1, 0, 0)),
             ((7, 6, 2, 3), (0, 1, 0)), ((0, 1, 5, 4), (0, -1, 0))]
    for piece in pieces:
        (x0, n0, u0), (x1, n1, u1) = piece["bounds_wir_m"]
        gx0, gx1 = -x1, -x0
        z0, z1 = n0, n1
        vertices = [(gx0, u0, z0), (gx1, u0, z0), (gx1, u1, z0), (gx0, u1, z0),
                    (gx0, u0, z1), (gx1, u0, z1), (gx1, u1, z1), (gx0, u1, z1)]
        positions, normals, indices = [], [], []
        for corner_ids, normal in faces:
            base = len(positions)
            positions.extend(vertices[i] for i in corner_ids)
            normals.extend([normal] * 4)
            indices.extend(base + i for i in (0, 1, 2, 0, 2, 3))
        pos_bytes = b"".join(struct.pack("<fff", *v) for v in positions)
        normal_bytes = b"".join(struct.pack("<fff", *v) for v in normals)
        index_bytes = b"".join(struct.pack("<H", i) for i in indices)
        pos = add_accessor(add_view(pos_bytes, 34962), 5126, len(positions), "VEC3",
                           [gx0, u0, z0], [gx1, u1, z1])
        norm = add_accessor(add_view(normal_bytes, 34962), 5126, len(normals), "VEC3")
        idx = add_accessor(add_view(index_bytes, 34963), 5123, len(indices), "SCALAR")
        mesh_id = len(doc["meshes"])
        doc["meshes"].append({"name": piece["name"], "primitives": [{
            "attributes": {"POSITION": pos, "NORMAL": norm}, "indices": idx,
            "material": piece["material"]}]})
        doc["nodes"].append({"name": piece["name"], "mesh": mesh_id,
                             "extras": {"source_id": piece["source_id"]}})
    while len(binary) % 4:
        binary.append(0)
    doc["buffers"].append({"byteLength": len(binary)})
    metadata = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    metadata += b" " * ((-len(metadata)) % 4)
    length = 12 + 8 + len(metadata) + 8 + len(binary)
    return (struct.pack("<4sII", b"glTF", 2, length) +
            struct.pack("<I4s", len(metadata), b"JSON") + metadata +
            struct.pack("<I4s", len(binary), b"BIN\x00") + binary)


def export_sample(package: dict, output_dir: str | Path) -> dict:
    validate_package(package)
    if package["manifest"]["revision_id"] != "revision_two_storey_001":
        raise SampleExportError("only the frozen two-storey revision is supported")
    source_hash = "sha256:" + hashlib.sha256(json.dumps(package, ensure_ascii=False, sort_keys=True,
                                                          separators=(",", ":")).encode("utf-8")).hexdigest()
    if source_hash != SOURCE_HASH:
        raise SampleExportError("source sample changed; review and version this mapping")
    pieces = _pieces()
    glb = _glb(pieces)
    report = {"record_type": "export_report", "id": "report_unity_library",
              "revision_id": "revision_two_storey_001", "target_profile_id": "profile_unity_6000324",
              "status": "succeeded_with_warnings",
              "coordinate_transform_row_major": [1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1],
              "items": [
                  {"source_id": "world_two_storey", "target_id": "scene:world_two_storey", "classification": "preserved", "message": "world identity in sidecar"},
                  {"source_id": "building_arcane_library", "target_id": "glb:building_parts", "classification": "approximated", "message": "shell, door, bay window, floors and roof are adapter policy"},
                  {"source_id": "room_reading_lower", "target_id": "sidecar:room_reading_lower", "classification": "approximated", "message": "room bounds retained; no source wall geometry"},
                  {"source_id": "room_archive_upper", "target_id": "sidecar:room_archive_upper", "classification": "approximated", "message": "room bounds retained; no source wall geometry"},
                  {"source_id": "stair_library_main", "target_id": "glb:stair_tread_*", "classification": "approximated", "message": "eight 0.5 m treads are adapter policy"},
                  {"source_id": "chair_reading_001", "target_id": "glb:chair_proxy", "classification": "approximated", "message": "linked chair GLB unavailable; cuboid proxy used"}],
              "summary": {"preserved": 1, "approximated": 5, "omitted": 0, "unsupported": 0, "failed": 0},
              "extensions": {"adapter_version": ADAPTER_VERSION, "target_load": "not_run",
                             "collision": "not_run", "walkthrough": "not_run"}}
    profile = {"record_type": "target_profile", "id": "profile_unity_6000324", "target": "unity",
               "target_version": UNITY_VERSION + "+urp-" + URP_VERSION + "+gltfast-" + GLTFAST_VERSION,
               "adapter_version": ADAPTER_VERSION,
               "configuration": {"meters_per_unit": 1, "x_axis": "east", "y_axis": "up", "z_axis": "north",
                                 "mesh_format": "glb-2.0", "terrain": "ordinary_mesh"},
               "declared_capabilities": ["mesh", "materials", "mesh_collider"], "extensions": {}}
    derived = copy.deepcopy(package)
    derived["records"].append(profile)
    derived["records"].append(report)
    next(r for r in derived["records"] if r["id"] == "spec_two_storey")["target_profile_ids"].append(profile["id"])
    validate_package(derived)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    files = {"library.glb": glb, "manifest.json": _canonical({
        "format": "unity-glb-sample-0.1", "source_revision_id": "revision_two_storey_001",
        "source_snapshot_hash": source_hash, "adapter_version": ADAPTER_VERSION,
        "target_profile_id": profile["id"], "unity_version": UNITY_VERSION,
        "urp_version": URP_VERSION, "gltfast_version": GLTFAST_VERSION,
        "glb_sha256": "sha256:" + hashlib.sha256(glb).hexdigest(),
        "pieces": pieces, "source_to_glb_row_major": [-1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1],
        "source_to_unity_row_major": report["coordinate_transform_row_major"],
        "target_load": "not_run", "collision": "not_run", "walkthrough": "not_run"}),
             "export_report.json": _canonical(report), "target_profile.json": _canonical(profile)}
    for filename, content in files.items():
        (output / filename).write_bytes(content)
    return {"output": str(output), "glb_sha256": hashlib.sha256(glb).hexdigest(),
            "piece_count": len(pieces)}
