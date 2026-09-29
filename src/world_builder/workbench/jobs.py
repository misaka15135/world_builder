"""Persistent job lifecycle independent of HTTP and browser components."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from threading import Event, RLock
import uuid

from world_builder.agents.contracts import AgentError, CONFIG_SCHEMA, ROOT, strict_json, validate_schema
from world_builder.agents.runtime import write_json
from . import runner

SAMPLE_PROMPT = "一条街旁的一栋两层木构商铺和一座公共大厅，都能进入，商铺上层可达。"
TERMINAL = {"succeeded", "failed", "cancelled", "interrupted"}
ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class ServiceError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code = status, code


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path, default=None):
    try:
        return strict_json(path.read_bytes())
    except (OSError, ValueError, AgentError):
        return default


class JobService:
    def __init__(self, root, config, *, execute=runner.execute, provider_factory=runner.provider_for):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.config = deepcopy(config)
        self.execute, self.provider_factory = execute, provider_factory
        self.lock, self.pool = RLock(), ThreadPoolExecutor(max_workers=1, thread_name_prefix="world-job")
        self.jobs, self.cancels = {}, {}
        for path in self.root.glob("*/job.json"):
            job = read_json(path)
            if not job or not ID_PATTERN.fullmatch(path.parent.name) or job.get("id") != path.parent.name:
                continue
            if job.get("status") not in TERMINAL:
                job.update(status="interrupted", phase="interrupted", updated_at=now(),
                           error={"code": "server.restarted", "message": "服务重启，运行未自动续费或续跑。可查看记录并回放。"})
                write_json(path, job)
            self.jobs[job["id"]] = job

    def close(self):
        with self.lock:
            for event in self.cancels.values():
                event.set()
        self.pool.shutdown(wait=True, cancel_futures=True)

    def _persist(self, job):
        write_json(self.root / job["id"] / "job.json", job)

    def _get(self, job_id):
        if not ID_PATTERN.fullmatch(job_id) or job_id not in self.jobs:
            raise ServiceError(404, "job.missing", "运行不存在。")
        return self.jobs[job_id]

    def list(self):
        with self.lock:
            return deepcopy(sorted(self.jobs.values(), key=lambda j: j["created_at"], reverse=True)[:100])

    def create(self, body):
        if not isinstance(body, dict):
            raise ServiceError(400, "input.object", "请求必须是 JSON 对象。")
        allowed = {"mode", "prompt", "region_m", "seed", "minecraft", "unity", "config", "api_key", "replay_id"}
        if set(body) - allowed or body.get("mode") not in {"api", "fixture", "replay"}:
            raise ServiceError(400, "input.fields", "未知字段或运行模式。")
        with self.lock:
            if any(j["status"] not in TERMINAL for j in self.jobs.values()):
                raise ServiceError(409, "job.busy", "已有运行进行中，请等待结束或取消。")
            mode = body["mode"]
            replay_path = None
            if mode == "replay":
                source = self._get(str(body.get("replay_id", "")))
                source_root = self.root / source["id"]
                if not (source_root / "output" / "calls").is_dir():
                    raise ServiceError(409, "replay.empty", "该运行没有可回放的调用记录。")
                spec = read_json(source_root / "input.json")
                config = read_json(source_root / "config.json")
                if spec is None or config is None:
                    raise ServiceError(409, "replay.metadata", "回放元数据不完整。")
                spec.update(mode="replay", replay_id=source["id"])
                replay_path = source_root / "output"
            else:
                config = deepcopy(body.get("config", self.config))
                spec = {"mode": mode, "prompt": body.get("prompt", SAMPLE_PROMPT if mode == "fixture" else ""),
                        "region_m": body.get("region_m", 32 if mode == "fixture" else 128),
                        "seed": body.get("seed", 1), "minecraft": body.get("minecraft", True),
                        "unity": body.get("unity", True)}
            validate_schema(config, CONFIG_SCHEMA, "config.schema")
            if not isinstance(spec["prompt"], str) or not 1 <= len(spec["prompt"].strip()) <= 20000:
                raise ServiceError(400, "input.prompt", "场景描述须为 1—20000 字。")
            if type(spec["region_m"]) is not int or not 32 <= spec["region_m"] <= 512 or spec["region_m"] % 16:
                raise ServiceError(400, "input.region", "边长须为 32—512 米且是 16 的倍数。")
            if type(spec["seed"]) is not int or not 0 <= spec["seed"] <= 2**53 - 1:
                raise ServiceError(400, "input.seed", "网页种子须为 0—9007199254740991 的整数。")
            if any(type(spec[k]) is not bool for k in ("minecraft", "unity")):
                raise ServiceError(400, "input.export", "导出选项必须是布尔值。")
            if mode == "fixture" and (spec["prompt"] != SAMPLE_PROMPT or spec["region_m"] != 32 or spec["seed"] != 1):
                raise ServiceError(400, "fixture.fixed", "人工样例仅用于固定 32 米、seed 1 的商铺与大厅场景。请切换 API 模式测试自己的描述。")
            key = body.get("api_key") or None
            if key is not None and (not isinstance(key, str) or len(key) > 8192 or "\n" in key or "\r" in key):
                raise ServiceError(400, "api.credential", "密钥格式无效。")
            provider = self.provider_factory(mode, config, api_key=key, replay_path=replay_path)
            job_id = uuid.uuid4().hex
            job = {"id": job_id, "mode": mode, "prompt": spec["prompt"], "region_m": spec["region_m"],
                   "seed": spec["seed"], "status": "running", "phase": "planning", "created_at": now(),
                   "updated_at": now(), "result": None, "error": None, "replay_id": spec.get("replay_id")}
            directory = self.root / job_id
            directory.mkdir()
            write_json(directory / "input.json", spec)
            write_json(directory / "config.json", config)
            self.jobs[job_id] = job
            self._persist(job)
            event = self.cancels[job_id] = Event()
            self.pool.submit(self._run, job_id, spec, config, provider, event)
            return deepcopy(job)

    def _run(self, job_id, spec, config, provider, cancel):
        def phase(value):
            with self.lock:
                self.jobs[job_id].update(phase=value, updated_at=now())
                self._persist(self.jobs[job_id])
        output = self.root / job_id / "output"
        try:
            result = self.execute(spec, config, provider, output, cancel.is_set, phase)
            update = {"status": "succeeded", "phase": "completed", "result": result}
        except Exception as exc:
            code = getattr(exc, "code", "execution.error")
            status = "cancelled" if code == "execution.cancelled" else "failed"
            update = {"status": status, "phase": status, "error": {"code": code, "message": str(exc)},
                      "result": read_json(output / "result.json")}
        finally:
            # Do not retain credentials in the in-memory job registry.
            if hasattr(provider, "key"):
                provider.key = ""
        with self.lock:
            self.jobs[job_id].update(**update, updated_at=now())
            self._persist(self.jobs[job_id])
            self.cancels.pop(job_id, None)

    def cancel(self, job_id):
        with self.lock:
            job = self._get(job_id)
            if job["status"] not in TERMINAL:
                self.cancels[job_id].set()
                job.update(status="cancelling", updated_at=now())
                self._persist(job)
            return deepcopy(job)

    def detail(self, job_id):
        with self.lock:
            job = deepcopy(self._get(job_id))
        output = self.root / job_id / "output"
        events = []
        try:
            for line in (output / "events.jsonl").read_text("utf-8").splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    pass  # A concurrent append may leave its last line incomplete.
        except OSError:
            pass
        job["events"] = events
        job["resources"] = self.resources(job_id)
        job["scene_available"] = (output / "repository/scene.world.json").is_file()
        return job

    def resources(self, job_id):
        self._get(job_id)
        output = (self.root / job_id / "output").resolve()
        items = []
        if output.exists():
            for path in sorted(output.rglob("*")):
                if (path.is_file() and path.resolve().is_relative_to(output)
                        and path.suffix in {".json", ".jsonl", ".worldpkg", ".glb", ".schem"}):
                    relative = path.relative_to(output).as_posix()
                    items.append({"path": relative, "bytes": path.stat().st_size,
                                  "kind": "call" if relative.startswith("calls/") else "artifact"})
        return items

    def resource_path(self, job_id, relative):
        # Public resource IDs must be members of the manifest, never arbitrary paths.
        if relative not in {item["path"] for item in self.resources(job_id)}:
            raise ServiceError(404, "resource.missing", "文件不存在或不在该运行的公开产物中。")
        root = (self.root / job_id / "output").resolve()
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ServiceError(403, "resource.path", "文件越界。")
        return path
