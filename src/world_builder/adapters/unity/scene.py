"""Bounded Unity proof for one scene-pipeline open space.

The source WIR remains independent of both targets. This export materialises
only its ground plan, so it is not a full scene or building adapter.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from world_builder.adapters.unity.sample import (_box, _canonical, _glb,
                                                 GLTFAST_VERSION, UNITY_VERSION, URP_VERSION)
from world_builder.wir.validator import validate_package

ADAPTER_VERSION = "0.1.0-scene-open-space.1"
MATERIALS = [
    ("paving_stone", (0.40, 0.42, 0.45, 1.0)),
    ("light_path", (0.75, 0.75, 0.72, 1.0)),
    ("glass_lamp", (0.62, 0.82, 0.88, 0.72)),
    ("wood_fixture", (0.43, 0.27, 0.14, 1.0)),
]


def export_open_space(package: dict, source_id: str, output_dir: str | Path) -> dict:
    """Export one identified open space as independently mapped cuboid meshes."""
    validate_package(package)
    matches = [record for record in package["records"] if record["record_type"] == "entity"
               and record["id"] == source_id and record["kind"] == "open_space"]
    if len(matches) != 1:
        raise ValueError(f"unity.open_space_source: expected one open space {source_id!r}")
    record = matches[0]
    plan = record["geometry"]
    if plan.get("representation") != "ground_plan":
        raise ValueError(f"unity.open_space_geometry: unsupported {source_id!r}")
    (x0, n0, _), (x1, n1, height) = record["bounds"]["min"], record["bounds"]["max"]
    if height < 0.4:
        raise ValueError(f"unity.open_space_height: {source_id!r} is too low for the path")
    pieces = [_box(source_id + "_paving", source_id, x0, x1, n0, n1, 0, 0.25, 0)]
    px0, pn0, px1, pn1 = plan["path"]["rect"]
    pieces.append(_box(source_id + "_path", source_id, x0 + px0, x0 + px1,
                       n0 + pn0, n0 + pn1, 0.25, 0.4, 1))
    for fixture in plan["fixtures"]:
        top = min(height, float(fixture["height_m"]))
        if top <= 0.25:
            raise ValueError(f"unity.open_space_fixture: {fixture['id']} has no height above paving")
        material = 2 if fixture["use"] == "lamp" else 3
        pieces.append(_box(fixture["id"], fixture["id"],
                           x0 + fixture["x0"], x0 + fixture["x1"],
                           n0 + fixture["y0"], n0 + fixture["y1"], 0.25, top, material))
    glb = _glb(pieces, MATERIALS)
    manifest = {
        "format": "unity-glb-scene-open-space-0.1",
        "adapter_version": ADAPTER_VERSION,
        "source_world_id": package["manifest"]["world_id"],
        "source_revision_id": package["manifest"]["revision_id"],
        "source_id": source_id,
        "source_snapshot_sha256": "sha256:" + hashlib.sha256(_canonical(package)).hexdigest(),
        "unity_version": UNITY_VERSION, "urp_version": URP_VERSION,
        "gltfast_version": GLTFAST_VERSION,
        "glb_sha256": "sha256:" + hashlib.sha256(glb).hexdigest(),
        "piece_count": len(pieces), "pieces": pieces,
        "source_to_unity_axes": {"x": "east", "y": "up", "z": "north"},
        "target_load": "not_run", "collision": "not_run",
        "limits": "one open space only; flat cuboid paving/path/fixtures; no terrain, buildings, NavMesh or player walkthrough",
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    (output / "open_space.glb").write_bytes(glb)
    (output / "manifest.json").write_bytes(_canonical(manifest))
    return manifest
