"""A scene survives the exchange format: archive it, read it back, export it.

Work order 018's `.worldpkg` replay. A scene package is only useful if it can be
stored and handed to another machine, and the assets it names are only useful if
their bytes travel with it: the first scene packages recorded a hash for the
terrain heightfield while dropping the bytes, and the hash described a different
object than the payload, so no repository would accept them. Both are fixed, and
this test pins the property that matters — the replayed package exports the same
schematics, byte for byte, as the package that was just assembled.
"""
from __future__ import annotations

import json

from world_builder.adapters.minecraft.city import export_city
from world_builder.adapters.minecraft.scene import project_for_minecraft
from world_builder.planning import (assemble_scene, compile_brief, design_sites, load_designs,
                                    load_setting_pack, plan_siting, plan_terrain)
from world_builder.storage.repository import Repository
from world_builder.storage.worldpkg import export_worldpkg, read_worldpkg

PROMPT = "海运港口，码头货轮和仓库"


def _harbour_package():
    pack = load_setting_pack("harbour")
    brief = compile_brief(PROMPT, seed=4)
    terrain = plan_terrain("harbour", seed=4, region_m=512, spacing_m=8)
    siting = plan_siting(brief, pack, terrain)
    designs, _, _ = design_sites(siting, pack, load_designs("harbour"), seed=4)
    return brief, pack, terrain, siting, tuple(designs)


def test_the_terrain_entity_carries_a_sampled_height_grid() -> None:
    """Work order 014: the heights travel with the package, not only in the store.

    The heightfield asset is content-addressed, so a target holding only the
    package cannot read its bytes. A coarse grid rides on the terrain entity so
    an adapter can lay stepped ground — and so the dry dock has something to
    cut into instead of the two flat layers.
    """
    brief, pack, terrain, siting, designs = _harbour_package()
    package = assemble_scene(brief, pack, terrain, siting, designs)
    geometry = next(r for r in package["records"] if r.get("kind") == "terrain")["geometry"]
    grid = geometry["height_grid_m"]
    # Coarser than the plan's own 8 m sampling, fine enough to read as relief:
    # the spacing was halved on 2026-09-29 (32 -> 16 m) because finer cells mean
    # shorter risers, so the ground got smoother at slightly fewer blocks.
    assert 8.0 <= geometry["height_grid_spacing_m"] <= 32.0
    # The grid may equal the plan's own sampling (8 m is the settled default) but
    # must never be finer: a target must not invent relief the plan does not have.
    assert len(grid) == len(grid[0]) and len(grid) <= len(terrain.heights), "at most the plan's sampling"
    flat = [value for row in grid for value in row]
    assert min(flat) >= terrain.stats["min_m"] - 1.0 and max(flat) <= terrain.stats["max_m"] + 1.0
    assert max(flat) - min(flat) > 0.0, "the sampled ground is not one flat height"


def test_a_scene_package_survives_the_worldpkg_round_trip(tmp_path) -> None:
    brief, pack, terrain, siting, designs = _harbour_package()
    repository = Repository(tmp_path / "repo")
    published = []

    def sink(record: dict, payload: bytes) -> None:
        content_hash, relative = repository.publish(payload)
        assert content_hash == record["content_hash"], "the hash describes the bytes that are written"
        assert relative == "assets/sha256/" + record["content_hash"][7:]
        published.append(record["id"])

    package = assemble_scene(brief, pack, terrain, siting, designs, asset_sink=sink)
    assert published == ["asset_heightfield"], "the heightfield is the one asset a scene carries"
    repository.commit(package, None)
    archive = tmp_path / "scene.worldpkg"
    checksum = export_worldpkg(repository, package["manifest"]["world_id"], archive)
    replayed, blobs = read_worldpkg(archive)
    assert checksum.startswith("sha256:") and len(blobs) == 1
    assert replayed == package, "the archive is the package, not a summary of it"
    assert (replayed["records"][0].get("extensions") or {}).get("scene_spec"), "the scene spec travels too"


def test_the_replayed_package_exports_the_same_blocks(tmp_path) -> None:
    brief, pack, terrain, siting, designs = _harbour_package()
    repository = Repository(tmp_path / "repo")
    package = assemble_scene(brief, pack, terrain, siting, designs,
                             asset_sink=lambda record, payload: repository.publish(payload))
    repository.commit(package, None)
    archive = tmp_path / "scene.worldpkg"
    export_worldpkg(repository, package["manifest"]["world_id"], archive)
    replayed, _ = read_worldpkg(archive)
    direct = export_city(project_for_minecraft(package), tmp_path / "direct", include_interiors=False)
    again = export_city(project_for_minecraft(replayed), tmp_path / "again", include_interiors=False)
    assert direct["non_air_blocks"] == again["non_air_blocks"] > 0
    direct_hashes = {chunk["id"]: chunk["schem_sha256"]
                     for chunk in json.loads((tmp_path / "direct" / "manifest.json").read_text("utf-8"))["chunks"]}
    again_hashes = {chunk["id"]: chunk["schem_sha256"]
                    for chunk in json.loads((tmp_path / "again" / "manifest.json").read_text("utf-8"))["chunks"]}
    assert direct_hashes and direct_hashes == again_hashes, "every chunk is byte-identical after the replay"
