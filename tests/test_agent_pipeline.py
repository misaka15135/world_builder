"""Behavioural gates for model-authored stages, failure boundaries and exports."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import struct
from threading import Barrier, Lock

import pytest
from jsonschema import Draft202012Validator

from world_builder.agents.cli import main
from world_builder.agents.compiler import compile_package, export_geometry, save_world
from world_builder.agents.contracts import (AgentError, ROOT, STAGES, canonical, contract_document,
                                           digest, response_schema, strict_json, validate_schema)
from world_builder.agents.providers import (APIProvider, Completion, FixtureProvider, ReplayProvider,
                                           decode_wire, load_config)
from world_builder.agents.runtime import Supervisor
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


def test_api_wire_and_secret_boundary(tmp_path, config, sample, monkeypatch):
    from world_builder.agents import providers
    config.update(endpoint="https://example.invalid/v1/chat/completions", model="user-selected-model")
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


@pytest.mark.parametrize("finish,refusal,usage", [("length", None, {}), ("stop", "declined", {}),
                                               ("stop", None, {"prompt_tokens": -1, "completion_tokens": 1})])
def test_api_refusal_truncation_and_bad_usage_fail_closed(finish, refusal, usage):
    wire = canonical({"choices": [{"finish_reason": finish, "message": {"content": "{}", "refusal": refusal}}], "usage": usage})
    with pytest.raises(AgentError):
        decode_wire(wire, "model", "chat_completions")


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
