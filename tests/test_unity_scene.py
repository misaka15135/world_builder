"""Check the bounded scene open-space GLB against its WIR source."""
from __future__ import annotations

import copy
import hashlib
import json
import struct
from pathlib import Path

import pytest

from world_builder.adapters.unity.scene import export_open_space


SOURCE = Path(__file__).resolve().parents[1] / "artifacts/scene-arcane-open-space-current/wir.json"


def test_open_space_export_preserves_source_identity_and_geometry(tmp_path: Path) -> None:
    package = json.loads(SOURCE.read_text(encoding="utf-8"))
    original = copy.deepcopy(package)
    manifest = export_open_space(package, "open_space_site_001", tmp_path / "plaza")
    assert package == original
    assert manifest["source_world_id"] == package["manifest"]["world_id"]
    assert manifest["source_revision_id"] == package["manifest"]["revision_id"]
    assert manifest["piece_count"] == 34
    assert manifest["target_load"] == manifest["collision"] == "not_run"

    pieces = manifest["pieces"]
    assert len({piece["name"] for piece in pieces}) == len(pieces)
    assert pieces[0]["bounds_wir_m"] == [[288.466, 206.281, 0], [329.156, 240.191, 0.25]]
    assert pieces[1]["bounds_wir_m"][0][2] == 0.25
    assert all(piece["bounds_wir_m"][1][2] <= 0.62 for piece in pieces)
    assert all(piece["source_id"] == "open_space_site_001" or
               piece["source_id"].startswith("site_001_") for piece in pieces)

    glb = (tmp_path / "plaza/open_space.glb").read_bytes()
    assert manifest["glb_sha256"] == "sha256:" + hashlib.sha256(glb).hexdigest()
    assert struct.unpack_from("<4sII", glb) == (b"glTF", 2, len(glb))
    json_size, tag = struct.unpack_from("<I4s", glb, 12)
    assert tag == b"JSON"
    doc = json.loads(glb[20:20 + json_size])
    assert [node["name"] for node in doc["nodes"]] == [piece["name"] for piece in pieces]
    assert [node["extras"]["source_id"] for node in doc["nodes"]] == [
        piece["source_id"] for piece in pieces]


def test_open_space_export_rejects_unknown_source_without_writing(tmp_path: Path) -> None:
    package = json.loads(SOURCE.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="unity.open_space_source"):
        export_open_space(package, "open_space_missing", tmp_path / "missing")
    assert not (tmp_path / "missing").exists()
