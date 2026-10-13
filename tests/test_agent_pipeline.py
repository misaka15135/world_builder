"""Behavioural gates for model-authored stages, failure boundaries and exports."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
from threading import Barrier, Lock
import urllib.error

import pytest
from jsonschema import Draft202012Validator

from world_builder.agents.cli import main
from world_builder.agents.compiler import compile_package, export_geometry, save_world
from world_builder.agents.contracts import (AgentError, ROOT, STAGES, canonical, contract_document,
                                           digest, response_schema, strict_json, validate_schema)
from world_builder.agents.providers import (APIProvider, Completion, FixtureProvider, ReplayProvider,
                                           _http_error_message, decode_wire, load_config)
from world_builder.agents.runtime import Supervisor
from world_builder.agents.brief_normalization import normalize_single_site_road
from world_builder.agents.bounded_json import parse_bounded_json
from world_builder.agents.geometry_normalization import deduplicate_same_material
from world_builder.agents.road_normalization import widen_short_roads
from world_builder.agents.compact_building import project_compact_building, available_entry_sides
from world_builder.agents.contracts import COMPACT_E_VERSION
from world_builder.agents.validation import check_plan
from world_builder.storage.worldpkg import read_worldpkg
from world_builder.wir.validator import load_and_validate
from test_minecraft_sample import _read_nbt, _indices


@pytest.fixture
def config():
    return load_config(ROOT / "config/agents.example.json")


@pytest.fixture
def sample():
    return strict_json((ROOT / "examples/agent_scene.responses.json").read_bytes())


def plans_from(sample):
    responses = sample["responses"]
    return {**{s: deepcopy(responses[s + ":scene"]) for s in ("A", "B", "C", "D", "F")},
            "E": {k[2:]: deepcopy(v) for k, v in responses.items() if k.startswith("E:")}}


def test_single_site_road_projection_preserves_text_and_rejects_ambiguity(sample):
    source = deepcopy(sample["responses"]["A:scene"])
    source["requirements"] = [deepcopy(source["requirements"][0]),
                              {"id": "walkable_street", "description": "道路连续接到商铺入口",
                               "programme": "可步行街道", "min_count": 1, "max_count": 1,
                               "interior_required": False}]
    original = deepcopy(source)
    normalized, moved = normalize_single_site_road(source)
    assert source == original
    assert moved == ["walkable_street"]
    assert len(normalized["requirements"]) == 1
    assert "道路连续接到商铺入口" in normalized["requirements"][0]["description"]
    assert "道路连续接到商铺入口" in normalized["acceptance_criteria"][-1]
    ambiguous = deepcopy(source)
    ambiguous["requirements"][1]["programme"] = "临街商铺建筑"
    assert normalize_single_site_road(ambiguous) == (ambiguous, [])
    multiple = deepcopy(source)
    multiple["requirements"].append(deepcopy(original["requirements"][0]))
    multiple["requirements"][-1]["id"] = "other_building"
    assert normalize_single_site_road(multiple) == (multiple, [])


def test_single_site_road_projection_is_opt_in_and_logged(tmp_path, config, sample):
    config["limits"]["max_sites"] = 1
    config["brief_normalization"] = "single_site_road_v1"
    def edit(request, response, n):
        if request["stage"] == "A":
            response["payload"]["requirements"] = [response["payload"]["requirements"][0],
                {"id": "walkable_street", "description": "连接建筑入口的步行道路",
                 "programme": "walkable street", "min_count": 1, "max_count": 1,
                 "interior_required": False}]
        return response
    provider = ScriptedProvider(edit)
    supervisor = Supervisor(provider, config, tmp_path / "normalized", region_m=32)
    supervisor.prompt = sample["prompt"]
    accepted = supervisor.ask("A", {})
    assert len(accepted["requirements"]) == 1
    request_id = provider.requests[0]["request_id"]
    manifest = strict_json((supervisor.root / "calls" / request_id[7:] / "normalization.json").read_bytes())
    assert manifest["moved_requirement_ids"] == ["walkable_street"]
    assert manifest["accepted_payload_sha256"] == digest(accepted)
    raw = strict_json((supervisor.root / "calls" / request_id[7:] / "response.json").read_bytes())
    assert len(raw["payload"]["requirements"]) == 2


def test_local_envelope_guidance_is_opt_in(tmp_path, config):
    base = Supervisor(ScriptedProvider(), config, tmp_path / "base", region_m=32)
    config["design_guidance"] = "local_envelope_v1"
    guided = Supervisor(ScriptedProvider(), config, tmp_path / "guided", region_m=32)
    assert "if D site Z bounds are [1, 5], local Z spans" not in base.skills["E"]
    assert "if D site Z bounds are [1, 5], local Z spans" in guided.skills["E"]
    assert digest(base.skills["E"]) != digest(guided.skills["E"])


def test_half_open_siting_guidance_is_opt_in(tmp_path, config):
    base = Supervisor(ScriptedProvider(), config, tmp_path / "base", region_m=32)
    config["siting_guidance"] = "half_open_boxes_v1"
    guided = Supervisor(ScriptedProvider(), config, tmp_path / "guided", region_m=32)
    assert "NEVER [4, 4]" not in base.skills["D"]
    assert "NEVER [4, 4]" in guided.skills["D"]
    assert digest(base.skills["D"]) != digest(guided.skills["D"])


def test_bounded_syntax_repair_only_accepts_unambiguous_json():
    value, repair = parse_bounded_json(b'{"a":1,"a":1}')
    assert value == {"a": 1} and repair["equal_duplicate_keys"]
    value, repair = parse_bounded_json(b'{"a":1}}')
    assert value == {"a": 1} and repair["extra_closing_brace"]
    value, repair = parse_bounded_json(b'{"a":1,"a":1}}')
    assert value == {"a": 1} and repair["equal_duplicate_keys"] and repair["extra_closing_brace"]
    assert parse_bounded_json(b'{"a":1}') == ({"a": 1}, None)
    for bad in (b'{"a":1,"a":2}', b'{"a":1', b'{"a":NaN}', b'```json\n{"a":1}\n```'):
        with pytest.raises(AgentError):
            parse_bounded_json(bad)


def test_catalogue_guidance_and_short_length_feedback(tmp_path, config):
    base = Supervisor(ScriptedProvider(), config, tmp_path / "base", region_m=32)
    config["catalogue_guidance"] = "concise_catalogue_v1"
    guided = Supervisor(ScriptedProvider(), config, tmp_path / "guided", region_m=32)
    assert "hard schema ceiling is 3,000" not in base.skills["C"]
    assert "hard schema ceiling is 3,000" in guided.skills["C"]
    with pytest.raises(AgentError) as exc:
        validate_schema({"text": "x" * 1001}, {"type": "object", "properties": {
            "text": {"type": "string", "maxLength": 1000}}, "required": ["text"]})
    assert "string length 1001 exceeds maxLength 1000" in str(exc.value)
    assert "x" * 100 not in str(exc.value)


def test_simple_design_guidance_and_collision_feedback(tmp_path, config, sample):
    config["design_guidance"] = "simple_nonoverlap_v1"
    guided = Supervisor(ScriptedProvider(), config, tmp_path / "guided", region_m=32)
    assert "A window is not an" in guided.skills["E"]
    plans = plans_from(sample)
    site = next(iter(plans["E"]))
    design = deepcopy(plans["E"][site])
    first = deepcopy(design["parts"][0])
    first["id"] = "extra_collision"
    design["parts"].append(first)
    with pytest.raises(AgentError) as exc:
        check_plan("E", design, plans, region_m=32, limits=config["limits"], scope_id=site)
    assert exc.value.code == "design.overlap"
    assert "extra_collision" in str(exc.value)


def test_clear_space_feedback_names_obstructing_parts(tmp_path, config, sample):
    config["design_guidance"] = "simple_nonoverlap_v2"
    guided = Supervisor(ScriptedProvider(), config, tmp_path / "guided", region_m=32)
    assert "The declared space box is wholly EMPTY air" in guided.skills["E"]
    plans = plans_from(sample)
    site = next(iter(plans["E"]))
    design = deepcopy(plans["E"][site])
    if not design["spaces"]:
        pytest.skip("Fixture has no E clear space")
    obstruction = deepcopy(design["parts"][0])
    obstruction["id"] = "obstruction"
    obstruction["role"] = "furniture"
    access = design["spaces"][0]["access_cell"]
    obstruction["bounds"] = {"min": access, "max": [v + 1 for v in access]}
    design["parts"].append(obstruction)
    with pytest.raises(AgentError) as exc:
        check_plan("E", design, plans, region_m=32, limits=config["limits"], scope_id=site)
    assert exc.value.code == "design.space_solid"
    assert "obstruction" in str(exc.value)


def test_same_material_dedup_keeps_union_and_does_not_hide_other_material(sample):
    design = deepcopy(next(iter(plans_from(sample)["E"].values())))
    original = deepcopy(design["parts"][0])
    duplicate = deepcopy(original)
    duplicate["id"] = "same_material_overlay"
    design["parts"].append(duplicate)
    normalized, manifest = deduplicate_same_material(design)
    assert manifest["fully_covered_ids"] == [original["id"]]
    assert len(normalized["parts"]) == len(design["parts"]) - 1
    assert normalized["parts"][-1] == duplicate
    different = deepcopy(design)
    different["parts"][-1]["material"] = "metal" if original["material"] != "metal" else "stone"
    untouched, report = deduplicate_same_material(different)
    assert untouched == different and report is None


def test_same_material_dedup_is_opt_in_and_journaled(tmp_path, config, sample):
    config["geometry_normalization"] = "same_material_overlap_v1"
    config["design_guidance"] = "simple_nonoverlap_v3"
    def edit(request, response, n):
        if request["stage"] == "E" and request["scope_id"] == "shop_01":
            overlay = deepcopy(response["payload"]["parts"][0])
            overlay["id"] = "same_material_overlay"
            response["payload"]["parts"].append(overlay)
        return response
    provider = ScriptedProvider(edit)
    supervisor, accepted = run(tmp_path, config, sample, provider)
    assert "entry_cell.z = touching_road.bounds.max[2]" in supervisor.skills["E"]
    assert accepted["plans"]["F"]["verdict"] == "accept"
    assert len(list(supervisor.root.glob("calls/*/geometry_normalization.json"))) == 1


def test_road_width_projection_requires_full_d_validation(tmp_path, config, sample):
    plans = plans_from(sample)
    proposal = deepcopy(plans["D"])
    proposal["roads"][0]["bounds"]["min"][1] += 1
    normalized, manifest = widen_short_roads(proposal, plans, region_m=32, limits=config["limits"])
    assert manifest["changed_road_ids"] == ["main"]
    assert normalized == plans["D"]
    bad_plans = deepcopy(plans)
    bad_plans["B"]["heights"][0][0] = 20
    unchanged, report = widen_short_roads(proposal, bad_plans, region_m=32, limits=config["limits"])
    assert unchanged == proposal and report is None

    config["road_normalization"] = "road_min_width_v1"
    def edit(request, response, n):
        if request["stage"] == "D":
            response["payload"]["roads"][0]["bounds"]["min"][1] += 1
        return response
    runner, accepted = run(tmp_path, config, sample, ScriptedProvider(edit))
    assert accepted["plans"]["F"]["verdict"] == "accept"
    assert len(list(runner.root.glob("calls/*/road_normalization.json"))) == 1


def test_compact_e_subcontract_projects_valid_room_and_rejects_wrong_side(config, sample):
    plans = plans_from(sample)
    assert available_entry_sides(plans, "hall_01") == ["south"]
    blueprint = {"site_id": "hall_01", "concept": "Simple timber hall",
                 "floor_material": "wood", "wall_material": "wood", "roof_material": "wood",
                 "entry_side": "south", "room_programme": "public hall"}
    projected = project_compact_building(blueprint, plans, "hall_01")
    check_plan("E", projected, plans, region_m=32, limits=config["limits"], scope_id="hall_01")
    assert projected["entry_cell"][2] == 1
    assert projected["routes"][0]["cells"][-1] == projected["spaces"][0]["access_cell"]
    assert response_schema("E", compact_e=True)["properties"]["contract_version"] == {"const": COMPACT_E_VERSION}
    assert response_schema("E")["properties"]["contract_version"] == {"const": "0.1.0"}
    blueprint["entry_side"] = "north"
    with pytest.raises(AgentError) as exc:
        project_compact_building(blueprint, plans, "hall_01")
    assert exc.value.code == "building.entry_side"


def test_compact_e_synthetic_pipeline_and_exact_replay(tmp_path, config, sample):
    config["building_projection"] = "compact_shell_v1"
    def edit(request, response, n):
        if request["stage"] == "E":
            response["contract_version"] = COMPACT_E_VERSION
            response["payload"] = {"site_id": request["scope_id"], "concept": "Simple timber shell",
                "floor_material": "wood", "wall_material": "wood", "roof_material": "wood",
                "entry_side": "south", "room_programme": "interior room"}
        return response
    original, accepted = run(tmp_path, config, sample, ScriptedProvider(edit))
    assert accepted["building_projection"] == "compact_shell_v1"
    assert len(list(original.root.glob("calls/*/building_projection.json"))) == 2
    package, _ = compile_package(accepted, config["limits"])
    assert package["records"]
    replay = Supervisor(ReplayProvider(original.root), config, tmp_path / "compact_replay", region_m=32)
    same = replay.run(sample["prompt"])
    assert same == accepted and replay.network_calls == 0


class ScriptedProvider(FixtureProvider):
    def __init__(self, edit=lambda r, p, n: p):
        super().__init__(ROOT / "examples/agent_scene.responses.json")
        self.requests = []
        self.counts = Counter()
        self.lock = Lock()
        self.edit = edit

    def complete(self, request, *, timeout_s):
        key = (request["stage"], request["scope_id"])
        with self.lock:
            self.requests.append(deepcopy(request))
            self.counts[key] += 1
            number = self.counts[key]
        completion = super().complete(request, timeout_s=timeout_s)
        response = strict_json(completion.raw)
        response = self.edit(request, response, number)
        return Completion(canonical(response), "scripted-test", 0, 0, "synthetic_fixture")


def run(tmp_path, config, sample, provider=None, name="run"):
    supervisor = Supervisor(provider or ScriptedProvider(), config, tmp_path / name, region_m=32)
    accepted = supervisor.run(sample["prompt"])
    return supervisor, accepted


def test_every_stage_is_provider_authored_and_skill_is_in_request(tmp_path, config, sample, monkeypatch):
    import world_builder.planning.brief as brief
    import world_builder.planning.terrain as terrain
    import world_builder.planning.siting as siting
    import world_builder.planning.designer as designer
    def forbidden(*args, **kwargs):
        pytest.fail("Old deterministic planning must not be a hidden fallback")
    for module, name in ((brief, "compile_brief"), (terrain, "plan_terrain"),
                         (siting, "plan_siting"), (designer, "design_sites"), (designer, "design")):
        monkeypatch.setattr(module, name, forbidden)
    provider = ScriptedProvider()
    supervisor, accepted = run(tmp_path, config, sample, provider)
    assert len(provider.requests) == 7
    assert {r["stage"] for r in provider.requests} == set(STAGES)
    assert all("name: world-agent-" in r["instructions"] for r in provider.requests)
    assert all("Architectural decisions" in r["instructions"] for r in provider.requests if r["stage"] == "E")
    assert [r["stage"] for r in provider.requests].index("D") > max(
        i for i, r in enumerate(provider.requests) if r["stage"] in ("B", "C"))
    assert accepted["plans"] == plans_from(sample)
    package, _ = compile_package(accepted, config["limits"])
    assert any(r.get("kind") == "stair" for r in package["records"])
    assert supervisor.usage()["network_calls"] == 0


def test_local_rejection_retries_only_affected_site_with_feedback(tmp_path, config, sample):
    def edit(request, response, n):
        if request["stage"] == "E" and request["scope_id"] == "shop_01" and n == 1:
            response["payload"]["parts"][0]["bounds"]["max"][0] = 100
        return response
    provider = ScriptedProvider(edit)
    _, accepted = run(tmp_path, config, sample, provider)
    assert len(provider.requests) == 8
    attempts = [r for r in provider.requests if r["stage"] == "E" and r["scope_id"] == "shop_01"]
    assert attempts[1]["feedback"][0]["code"] == "design.envelope"
    assert accepted["plans"]["E"]["shop_01"]["parts"][0]["bounds"]["max"][0] == 8


@pytest.mark.parametrize("stage,scope,expected", [("E", "shop_01", 9), ("B", "scene", 12),
                                                 ("C", "scene", 12), ("D", "scene", 11)])
def test_f_review_invalidates_only_dependencies(tmp_path, config, sample, stage, scope, expected):
    def edit(request, response, n):
        if request["stage"] == "F" and n == 1:
            response["payload"].update(verdict="revise", accepted_sites=[],
                                       fixes=[{"stage": stage, "scope_id": scope, "reason": "Reassess architectural intent"}])
        return response
    provider = ScriptedProvider(edit)
    _, accepted = run(tmp_path, config, sample, provider)
    assert len(provider.requests) == expected
    assert provider.counts[("A", "scene")] == 1
    assert provider.counts[("E", "hall_01")] == (1 if stage == "E" else 2)
    assert accepted["plans"]["F"]["verdict"] == "accept"
    assert set(accepted["accepted_responses"]) == {"A:scene", "B:scene", "C:scene", "D:scene", "E:hall_01", "E:shop_01", "F:scene"}


def test_byte_exact_replay_and_worldpkg_geometry_roundtrip(tmp_path, config, sample):
    original, accepted = run(tmp_path, config, sample)
    result = save_world(accepted, original.root, config["limits"], minecraft=True, unity=True)
    replay, same = run(tmp_path, config, sample, ReplayProvider(original.root), name="replayed")
    assert same == accepted
    other = save_world(same, replay.root, config["limits"], minecraft=True, unity=True)
    assert result == other
    assert (original.root / "unity/scene.glb").read_bytes() == (replay.root / "unity/scene.glb").read_bytes()
    assert (original.root / "minecraft/agent_0_-1.schem").read_bytes() == (replay.root / "minecraft/agent_0_-1.schem").read_bytes()
    package, blobs = read_worldpkg(original.root / "scene.worldpkg")
    assert len(blobs) == 1
    assert load_and_validate(original.root / "repository/scene.world.json") == package
    again = export_geometry(package, tmp_path / "from_archive", config["limits"], minecraft=True, unity=True)
    assert again == result["exports"]
    glb = (original.root / "unity/scene.glb").read_bytes()
    assert struct.unpack_from("<4sII", glb) == (b"glTF", 2, len(glb))
    json_size = struct.unpack_from("<I", glb, 12)[0]
    gltf = json.loads(glb[20:20 + json_size])
    assert len(gltf["meshes"]) == 45
    assert all(n["extras"]["source_id"] for n in gltf["nodes"])
    nbt = _read_nbt(gzip.decompress((original.root / "minecraft/agent_0_-1.schem").read_bytes()))["Schematic"]
    assert nbt["Version"] == 3 and nbt["DataVersion"] == 4671
    indices = _indices(nbt["Blocks"]["Data"])
    palette = {v: k for k, v in nbt["Blocks"]["Palette"].items()}
    def block(x, north, up):
        # WIR cell [north,north+1) maps to Minecraft [-north-1,-north).
        z = 127 - north
        return palette[indices[x + z * 128 + up * 128 * 128]]
    for site in sample["responses"]["D:scene"]["sites"]:
        design = sample["responses"]["E:" + site["id"]]
        for route in design["routes"]:
            for cell in route["cells"]:
                x, north, up = [cell[i] + site["bounds"]["min"][i] for i in range(3)]
                assert block(x, north, up) == block(x, north, up + 1) == "minecraft:air"
                assert block(x, north, up - 1) != "minecraft:air"
    report = strict_json((original.root / "minecraft/export_report.json").read_bytes())
    assert len(report["items"]) == sum(r["record_type"] == "entity" for r in package["records"])
    assert replay.usage()["network_calls"] == 0


def test_replay_refuses_changed_prompt_and_tampered_response(tmp_path, config, sample):
    original, _ = run(tmp_path, config, sample)
    runner = Supervisor(ReplayProvider(original.root), config, tmp_path / "changed", region_m=32)
    with pytest.raises(AgentError, match="No recorded response"):
        runner.run(sample["prompt"] + " another request")
    call = next(p for p in (original.root / "calls").iterdir()
                if json.loads((p / "request.json").read_text("utf-8"))["stage"] == "A")
    (call / "response.json").write_bytes(b"{}")
    runner = Supervisor(ReplayProvider(original.root), config, tmp_path / "tampered", region_m=32)
    with pytest.raises(AgentError, match="hash differs"):
        runner.run(sample["prompt"])


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'```json\n{}\n```', b'{"x":Infinity}', b'{"x":1e999}'])
def test_untrusted_json_is_not_coerced_or_repaired(raw):
    with pytest.raises(AgentError):
        strict_json(raw)


def test_schema_refuses_unknown_fields_and_cross_scope_response(sample):
    response = {"contract_version": "0.1.0", "stage": "A", "request_id": digest("input"),
                "scope_id": "scene", "payload": sample["responses"]["A:scene"]}
    schema = response_schema("A", response["request_id"], "scene")
    for change in ({"stage": "F"}, {"scope_id": "other"}, {"execute": "arbitrary code"}):
        with pytest.raises(AgentError):
            validate_schema({**response, **change}, schema)
    Draft202012Validator.check_schema(contract_document())
    assert strict_json((ROOT / "schemas/agent-response-0.1.0.schema.json").read_bytes()) == contract_document()


def test_a_site_budget_keeps_hard_limit_but_allows_model_retry(tmp_path, config, sample):
    config["limits"].update(max_sites=4, attempts=2)
    def split_features_into_sites(request, response, number):
        if request["stage"] == "A":
            requirements = response["payload"]["requirements"]
            for suffix in ("road", "entrance", "room"):
                item = deepcopy(requirements[0])
                item["id"] = suffix
                requirements.append(item)
        return response
    provider = ScriptedProvider(split_features_into_sites)
    with pytest.raises(AgentError) as exc:
        run(tmp_path, config, sample, provider)
    assert exc.value.code == "stage.exhausted"
    assert "brief.site_budget" in str(exc.value)
    assert provider.counts[("A", "scene")] == 2


@pytest.mark.parametrize("case", ["missing_type", "missing_site", "floating_site", "road_through_site",
                                 "solid_room", "blocked_door", "teleport", "missing_floor_path", "forged_approval"])
def test_semantic_failures_are_not_overridden_by_f(config, sample, case):
    plans = plans_from(sample)
    stage, scope = "D", "scene"
    if case == "missing_type":
        stage = "C"
        plans["C"]["types"].pop()
    elif case == "missing_site":
        plans["D"]["sites"].pop()
    elif case == "floating_site":
        plans["D"]["sites"][0]["bounds"]["min"][2] = 3
    elif case == "road_through_site":
        plans["D"]["roads"][0]["bounds"]["max"][1] = 5
    elif case == "forged_approval":
        stage = "F"
        plans["F"]["accepted_sites"].pop()
    else:
        stage, scope = "E", "shop_01"
        design = plans["E"][scope]
        if case == "solid_room":
            design["spaces"][0]["bounds"]["min"][0] = 0
        elif case == "blocked_door":
            design["parts"][3]["bounds"]["min"][2] = 1
        elif case == "teleport":
            design["routes"][0]["cells"] = [[3,0,1], [3,3,1]]
        elif case == "missing_floor_path":
            design["spaces"].pop()
            design["routes"].pop()
    with pytest.raises(AgentError):
        check_plan(stage, plans[stage] if stage != "E" else plans[stage][scope], plans,
                   region_m=32, limits=config["limits"], scope_id=scope)


def test_failure_preserves_evidence_without_dropping_the_site(tmp_path, config, sample):
    def edit(request, response, n):
        if request["stage"] == "E":
            response["payload"]["routes"] = []
        return response
    provider = ScriptedProvider(edit)
    runner = Supervisor(provider, config, tmp_path / "bad", region_m=32)
    with pytest.raises(AgentError) as exc:
        runner.run(sample["prompt"])
    assert exc.value.code == "stage.exhausted"
    assert (runner.root / "failure.json").exists()
    assert not (runner.root / "accepted.json").exists()
    assert not provider.counts[("F", "scene")]


def test_budgets_time_cancellation_and_output_collision(tmp_path, config, sample):
    for field, value, code in (("max_calls", 6, "budget.calls"), ("max_total_tokens", 1000, "budget.tokens")):
        config["limits"][field] = value
        runner = Supervisor(ScriptedProvider(), config, tmp_path / field, region_m=32)
        with pytest.raises(AgentError) as exc:
            runner.run(sample["prompt"])
        assert exc.value.code == code
        config = load_config(ROOT / "config/agents.example.json")
    runner = Supervisor(ScriptedProvider(), config, tmp_path / "cancel", region_m=32, cancelled=lambda: True)
    with pytest.raises(AgentError) as exc:
        runner.run(sample["prompt"])
    assert exc.value.code == "execution.cancelled" and runner.calls == 0
    with pytest.raises(FileExistsError):
        Supervisor(ScriptedProvider(), config, runner.root, region_m=32)
    times = iter([0, config["limits"]["wall_time_s"] + 1])
    runner = Supervisor(ScriptedProvider(), config, tmp_path / "timeout", region_m=32, clock=lambda: next(times))
    with pytest.raises(AgentError) as exc:
        runner.run(sample["prompt"])
    assert exc.value.code == "budget.time"


def test_provider_placeholder_is_rejected_before_any_network(config, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Placeholder must not reach network")
    monkeypatch.setattr("urllib.request.build_opener", forbidden)
    with pytest.raises(AgentError) as exc:
        APIProvider(config)
    assert exc.value.code == "api.placeholder"


def test_http_error_hint_redacts_key_and_bounds_untrusted_body():
    key = "sk-private-key-12345678"
    body = canonical({"error": {"type": "invalid_request_error", "code": "invalid_format",
                                "message": "bad field for " + key + " " + "x" * 1000}})
    error = urllib.error.HTTPError("https://api.deepseek.com/chat/completions", 400,
                                   "Bad Request", {}, io.BytesIO(body))
    message = _http_error_message(error, key)
    assert "HTTP 400" in message and "invalid_format" in message
    assert key not in message and "[redacted]" in message
    assert len(message) < 400


@pytest.mark.parametrize("thinking,endpoint", [(None, "https://example.invalid/v1/chat/completions"),
                                                   ("disabled", "https://api.deepseek.com/chat/completions")])
def test_api_wire_and_secret_boundary(tmp_path, config, sample, monkeypatch, thinking, endpoint):
    from world_builder.agents import providers
    config.update(endpoint=endpoint, model="user-selected-model")
    if thinking:
        config["deepseek_thinking"] = thinking
    monkeypatch.setenv("WORLD_BUILDER_API_KEY", "test-secret-never-log")
    requests = []
    class Response:
        status = 200
        def __init__(self, blob): self.blob = blob
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return self.blob[:limit]
    class Opener:
        def open(self, req, timeout):
            body = strict_json(req.data)
            assert req.headers["Authorization"] == "Bearer test-secret-never-log"
            assert body["response_format"] == {"type": "json_object"}
            assert body["max_completion_tokens"] == config["limits"]["max_output_tokens"]
            assert body.get("thinking") == ({"type": thinking} if thinking else None)
            data = strict_json(body["messages"][1]["content"])
            requests.append(data)
            envelope = {k: data[k] for k in ("contract_version", "stage", "request_id", "scope_id")}
            envelope["payload"] = sample["responses"][data["stage"] + ":" + data["scope_id"]]
            return Response(canonical({"model": body["model"], "choices": [{"finish_reason": "stop", "message": {"content": canonical(envelope).decode()}}],
                                       "usage": {"prompt_tokens": 100, "completion_tokens": 200}}))
    monkeypatch.setattr(providers.urllib.request, "build_opener", lambda *args: Opener())
    supervisor, _ = run(tmp_path, config, sample, APIProvider(config))
    assert len(requests) == supervisor.network_calls == 7
    assert supervisor.token_usage == 2100
    assert not any(b"test-secret-never-log" in p.read_bytes() for p in supervisor.root.rglob("*.json"))


def test_deepseek_responses_schema_wire_and_secret_boundary(tmp_path, config, sample, monkeypatch):
    from world_builder.agents import providers
    config.update(endpoint="https://api.deepseek.com/responses", model="deepseek-flash",
                  protocol="responses", response_format="json_schema", deepseek_reasoning="none")
    monkeypatch.setenv("WORLD_BUILDER_API_KEY", "test-secret-never-log")
    requests = []
    class Response:
        status = 200
        def __init__(self, blob): self.blob = blob
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return self.blob[:limit]
    class Opener:
        def open(self, req, timeout):
            body = strict_json(req.data)
            assert body["store"] is False and body["stream"] is False
            assert body["reasoning"] == {"effort": "none"}
            assert body["text"]["format"]["type"] == "json_schema"
            assert body["max_output_tokens"] == config["limits"]["max_output_tokens"]
            data = strict_json(body["input"])
            assert "name: world-agent-" in body["instructions"] and "instructions" not in data
            assert body["text"]["format"]["schema"] == {k: v for k, v in data["response_schema"].items() if k != "$schema"}
            requests.append(data)
            envelope = {k: data[k] for k in ("contract_version", "stage", "request_id", "scope_id")}
            envelope["payload"] = sample["responses"][data["stage"] + ":" + data["scope_id"]]
            return Response(canonical({"status": "completed", "model": "deepseek-flash",
                "output": [{"type": "message", "status": "completed", "role": "assistant",
                            "content": [{"type": "output_text", "text": canonical(envelope).decode()}]}],
                "usage": {"input_tokens": 100, "output_tokens": 200}}))
    monkeypatch.setattr(providers.urllib.request, "build_opener", lambda *args: Opener())
    supervisor, _ = run(tmp_path, config, sample, APIProvider(config))
    assert len(requests) == supervisor.network_calls == 7
    assert supervisor.token_usage == 2100
    assert not any(b"test-secret-never-log" in p.read_bytes() for p in supervisor.root.rglob("*.json"))


def test_deepseek_responses_incomplete_and_tool_output_fail_closed():
    wire = canonical({"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
                      "usage": {"input_tokens": 10, "output_tokens": 16000}, "output": []})
    with pytest.raises(AgentError) as incomplete:
        decode_wire(wire, "deepseek-flash", "responses")
    assert incomplete.value.code == "api.incomplete"
    assert incomplete.value.details == {"reason": "max_output_tokens",
                                        "provider_usage": {"input_tokens": 10, "output_tokens": 16000}}
    wire = canonical({"status": "completed", "usage": {"input_tokens": 10, "output_tokens": 5},
                      "output": [{"type": "function_call", "status": "completed"}]})
    with pytest.raises(AgentError) as tool:
        decode_wire(wire, "deepseek-flash", "responses")
    assert tool.value.code == "api.content"


@pytest.mark.parametrize("finish,refusal,usage", [("length", None, {}), ("stop", "declined", {}),
                                               ("stop", None, {"prompt_tokens": -1, "completion_tokens": 1})])
def test_api_refusal_truncation_and_bad_usage_fail_closed(finish, refusal, usage):
    wire = canonical({"choices": [{"finish_reason": finish, "message": {"content": "{}", "refusal": refusal}}], "usage": usage})
    with pytest.raises(AgentError):
        decode_wire(wire, "model", "chat_completions")


@pytest.mark.parametrize("finish,usage,expected", [
    ("length", {"prompt_tokens": 120, "completion_tokens": 16000},
     {"input_tokens": 120, "output_tokens": 16000}),
    ("content_filter", {}, None),
    ("unrecognised-provider-reason", {"prompt_tokens": -1, "completion_tokens": 4}, None),
])
def test_incomplete_response_keeps_safe_diagnostics(finish, usage, expected):
    wire = canonical({"choices": [{"finish_reason": finish, "message": {"content": "private response"}}],
                      "usage": usage})
    with pytest.raises(AgentError) as exc:
        decode_wire(wire, "model", "chat_completions")
    assert exc.value.code == "api.incomplete"
    assert exc.value.details == {"finish_reason": finish if finish != "unrecognised-provider-reason" else "unknown",
                                 "choice_count": 1, "provider_usage": expected}
    assert "private response" not in str(exc.value)


def test_incomplete_response_diagnostics_survive_failure_and_replay(tmp_path, config, sample):
    config["limits"]["attempts"] = 1
    class PartialProvider:
        network = True
        def complete(self, request, *, timeout_s):
            wire = canonical({"choices": [{"finish_reason": "length", "message": {"content": "private response"}}],
                              "usage": {"prompt_tokens": 120, "completion_tokens": 16000}})
            return decode_wire(wire, "model", "chat_completions")
    runner = Supervisor(PartialProvider(), config, tmp_path / "incomplete", region_m=32)
    with pytest.raises(AgentError) as failed:
        runner.run(sample["prompt"])
    assert failed.value.code == "stage.exhausted"
    error_file = next((runner.root / "calls").glob("*/error.json"))
    error = strict_json(error_file.read_bytes())
    assert error == {"code": "api.incomplete", "message": "Provider response incomplete (finish_reason=length)",
                     "details": {"finish_reason": "length", "choice_count": 1,
                                 "provider_usage": {"input_tokens": 120, "output_tokens": 16000}}}
    assert "private response" not in error_file.read_text("utf-8")
    replay = Supervisor(ReplayProvider(runner.root), config, tmp_path / "replayed_failure", region_m=32)
    with pytest.raises(AgentError) as replay_failed:
        replay.run(sample["prompt"])
    assert replay_failed.value.code == "stage.exhausted"
    replay_error = next((replay.root / "calls").glob("*/error.json"))
    assert strict_json(replay_error.read_bytes()) == error


def test_cli_fixture_is_explicit_and_placeholder_does_not_write(tmp_path, sample):
    output = tmp_path / "placeholder"
    assert main(["--prompt", sample["prompt"], "--output", str(output)]) == 1
    assert not output.exists()
    output = tmp_path / "fixture"
    assert main(["--prompt", sample["prompt"], "--region-m", "32", "--output", str(output),
                 "--fixtures", str(ROOT / "examples/agent_scene.responses.json"), "--minecraft", "--unity"]) == 0
    result = strict_json((output / "result.json").read_bytes())
    assert result["mode"] == "synthetic_fixture" and result["network_calls"] == 0


def test_b_c_and_per_site_e_really_run_concurrently(tmp_path, config, sample):
    bc, es = Barrier(2), Barrier(2)
    def edit(request, response, n):
        if request["stage"] in ("B", "C"):
            bc.wait(timeout=5)
        if request["stage"] == "E":
            es.wait(timeout=5)
        return response
    supervisor, _ = run(tmp_path, config, sample, ScriptedProvider(edit))
    assert supervisor.calls == 7


def test_f_cannot_create_endless_rework(tmp_path, config, sample):
    config["limits"]["review_rounds"] = 1
    def edit(request, response, n):
        if request["stage"] == "F":
            response["payload"].update(verdict="revise", accepted_sites=[],
                fixes=[{"stage": "E", "scope_id": "shop_01", "reason": "Still not acceptable"}])
        return response
    runner = Supervisor(ScriptedProvider(edit), config, tmp_path / "loop", region_m=32)
    with pytest.raises(AgentError) as exc:
        runner.run(sample["prompt"])
    assert exc.value.code == "review.exhausted" and runner.calls == 9
    assert not (runner.root / "accepted.json").exists()


def test_output_memory_budget_fails_before_world_commit(tmp_path, config, sample):
    runner, accepted = run(tmp_path, config, sample)
    config["limits"]["max_voxels"] = 1000
    with pytest.raises(AgentError) as exc:
        save_world(accepted, runner.root, config["limits"], minecraft=True)
    assert exc.value.code == "budget.voxels"
    assert not (runner.root / "scene.worldpkg").exists()


def test_json_contract_protocol_preserves_response_bytes_semantics(sample):
    envelope = {"contract_version": "0.1.0", "stage": "A", "scope_id": "scene", "request_id": digest("r"),
                "payload": sample["responses"]["A:scene"]}
    wire = canonical({"model": "private-service", "response": envelope,
                      "usage": {"input_tokens": 101, "output_tokens": 202}})
    completed = decode_wire(wire, "configured-model", "json_contract")
    assert strict_json(completed.raw) == envelope
    assert (completed.input_tokens, completed.output_tokens) == (101, 202)


def test_integral_json_number_notation_is_valid():
    assert strict_json(b'{"a":1.0,"b":2e0}') == {"a": 1, "b": 2}
