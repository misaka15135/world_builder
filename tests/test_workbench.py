"""HTTP and job boundaries for the local workbench; no paid network calls."""
from copy import deepcopy
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
from threading import Event, Thread
import time

import pytest

from world_builder.agents.contracts import AgentError, ROOT
from world_builder.agents.providers import APIProvider, FixtureProvider, load_config
from world_builder.agents.runtime import write_json
from world_builder.workbench.jobs import JobService, SAMPLE_PROMPT, ServiceError, TERMINAL
from world_builder.workbench.server import RootLock, WorkbenchServer


@pytest.fixture
def config():
    return load_config(ROOT / "config/agents.example.json")


def complete(service, job_id):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        job = service.detail(job_id)
        if job["status"] in TERMINAL:
            return job
        time.sleep(.02)
    pytest.fail("Job did not terminate")


@pytest.fixture
def service(tmp_path, config):
    instance = JobService(tmp_path / "runs", config)
    yield instance
    instance.close()


def test_full_fixture_replay_history_and_download_resources(service, config):
    first = complete(service, service.create({"mode": "fixture"})["id"])
    assert first["status"] == "succeeded" and first["scene_available"]
    assert first["result"]["provider_calls"] == 7 and first["result"]["network_calls"] == 0
    assert {e["stage"] for e in first["events"] if e["event"] == "accepted"} == set("ABCDEF")
    assert first["result"]["exports"]["unity"]["mesh_count"] == 45
    second = complete(service, service.create({"mode":"replay", "replay_id":first["id"], "prompt":"ignored new prompt"})["id"])
    assert second["status"] == "succeeded" and second["prompt"] == SAMPLE_PROMPT
    for path in ("scene.worldpkg", "unity/scene.glb", "repository/scene.world.json"):
        assert service.resource_path(first["id"], path).read_bytes() == service.resource_path(second["id"], path).read_bytes()
    restored = JobService(service.root, config)
    try:
        assert len(restored.list()) == 2 and restored.detail(first["id"])["status"] == "succeeded"
    finally:
        restored.close()


@pytest.mark.parametrize("body", [None, [], {"mode":"unknown"}, {"mode":"fixture","extra":1},
    {"mode":"fixture","region_m":33}, {"mode":"fixture","seed":-1},
    {"mode":"fixture","seed":2**53}, {"mode":"fixture","minecraft":"yes"},
    {"mode":"fixture","prompt":"a different scene"}, {"mode":"fixture","prompt":""}])
def test_invalid_input_creates_no_job(service, body):
    with pytest.raises(ServiceError):
        service.create(body)
    assert service.list() == []


def test_placeholder_fails_before_job_or_network(service):
    with pytest.raises(AgentError, match="Replace yourapi"):
        service.create({"mode":"api", "prompt":"a town"})
    assert service.list() == []


def test_cancel_and_single_active_run(tmp_path, config):
    started = Event()
    def execute(spec, config, provider, output, cancelled, phase):
        started.set()
        for _ in range(200):
            if cancelled():
                raise AgentError("execution.cancelled", "Cancelled")
            time.sleep(.01)
        raise AssertionError("Cancellation not observed")
    service = JobService(tmp_path, config, execute=execute)
    try:
        job = service.create({"mode":"fixture"})
        assert started.wait(2)
        with pytest.raises(ServiceError) as error:
            service.create({"mode":"fixture"})
        assert error.value.status == 409
        service.cancel(job["id"])
        result = complete(service, job["id"])
        assert result["status"] == "cancelled" and result["error"]["code"] == "execution.cancelled"
        assert service.cancel(job["id"])["status"] == "cancelled"
    finally:
        service.close()


def test_restart_preserves_interrupted_evidence(tmp_path, config):
    job_id = "a" * 32
    write_json(tmp_path / job_id / "job.json", {"id":job_id, "status":"running", "phase":"planning", "created_at":"2026-09-29"})
    service = JobService(tmp_path, config)
    try:
        job = service.detail(job_id)
        assert job["status"] == "interrupted" and job["error"]["code"] == "server.restarted"
    finally:
        service.close()


def test_per_run_credential_does_not_touch_environment_or_disk(tmp_path, config, monkeypatch):
    config.update(endpoint="https://example.test/v1/chat/completions",model="model-test")
    monkeypatch.setenv(config["api_key_env"], "existing-environment-value")
    import os
    assert APIProvider(config,api_key="one-time-secret").key == "one-time-secret"
    assert os.environ[config["api_key_env"]] == "existing-environment-value"
    captured = []
    def factory(mode, cfg, api_key, replay_path):
        captured.append(api_key)
        return FixtureProvider(ROOT / "examples/agent_scene.responses.json")
    service = JobService(tmp_path, config, provider_factory=factory)
    try:
        job = complete(service, service.create({"mode":"api","prompt":SAMPLE_PROMPT,"region_m":32,"api_key":"one-time-secret"})["id"])
        assert job["status"] == "succeeded" and captured == ["one-time-secret"]
        for path in tmp_path.rglob("*.json"):
            assert b"one-time-secret" not in path.read_bytes()
    finally:
        service.close()


@pytest.fixture
def http(service):
    server = WorkbenchServer(("127.0.0.1",0), service)
    thread = Thread(target=server.serve_forever,daemon=True); thread.start()
    def call(path, body=None, **headers):
        connection = HTTPConnection("127.0.0.1",server.server_port,timeout=5)
        request_headers = {"Content-Type":"application/json"}
        request_headers.update(headers)
        connection.request("GET" if body is None else "POST",path,
                           body=None if body is None else json.dumps(body),headers=request_headers)
        response = connection.getresponse(); raw = response.read()
        result = response.status, dict(response.getheaders()), raw
        connection.close()
        return result
    yield server, call
    server.shutdown(); server.server_close(); thread.join(2)


def test_http_bootstrap_assets_and_csrf(http):
    server, call = http
    status, headers, raw = call("/api/v1/bootstrap")
    data=json.loads(raw)
    assert status == 200 and len(data["skills"]) == 6
    assert headers["Cache-Control"] == "no-store"
    assert call("/mark.svg")[1]["Content-Type"] == "image/svg+xml"
    assert call("/app.js")[1]["Content-Type"] == "text/javascript"
    assert call("/api/v1/jobs", {"mode":"fixture"})[0] == 403
    assert call("/api/v1/jobs", {"mode":"fixture"}, **{"X-Workbench-Token":data["session_token"],"Origin":"https://untrusted.test"})[0] == 403
    assert call("/api/v1/jobs", Host="untrusted.test")[0] == 403
    assert call("/../config/agents.example.json")[0] == 404
    assert call("/api/v1/jobs/not-an-id")[0] == 404
    assert call("/api/v1/contracts/E")[0] == 200
    assert data["skills"][4]["text"].endswith((ROOT / "skills/world-agent-e/references/design-principles.md").read_text("utf-8"))


def test_config_validation_is_local_and_rejects_extra_fields(http, service, config):
    server, call = http
    headers = {"X-Workbench-Token":server.token}
    assert call("/api/v1/config/validate",config,**headers)[0] == 200
    config["secret"] = "do-not-save"
    assert call("/api/v1/config/validate",config,**headers)[0] == 400
    assert service.list() == []


def test_http_create_scene_document_download_and_traversal(http, service):
    server, call = http
    status, _, raw = call("/api/v1/jobs",{"mode":"fixture"},**{"X-Workbench-Token":server.token,"Origin":server.origin})
    assert status == 202
    job = complete(service, json.loads(raw)["id"])
    base=f"/api/v1/jobs/{job['id']}"
    status, _, raw = call(base + "/scene")
    assert status == 200 and len(json.loads(raw)["records"]) > 45
    assert call(base+"/document?path=result.json")[0] == 200
    status, headers, raw = call(base+"/file?path=scene.worldpkg")
    assert status == 200 and "attachment" in headers["Content-Disposition"]
    assert "sha256:"+hashlib.sha256(raw).hexdigest() == job["result"]["worldpkg_sha256"]
    for path in ["../../config.json", "repository/wir.sqlite3", "../job.json"]:
        assert call(base+"/file?path="+path)[0] == 404
    assert call(base+"/document?path=unity/scene.glb")[0] == 413


def test_two_servers_cannot_recover_same_run_directory(tmp_path):
    first = RootLock(tmp_path)
    try:
        with pytest.raises(RuntimeError):
            RootLock(tmp_path)
    finally:
        first.close()
    second=RootLock(tmp_path); second.close()


def test_invalid_schema_cannot_persist_credentials(service, config):
    config["api_key"]="badly-placed-secret"
    with pytest.raises(AgentError):
        service.create({"mode":"fixture","config":config})
    assert service.list() == []
