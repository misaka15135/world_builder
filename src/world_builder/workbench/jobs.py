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
from urllib.parse import urlsplit

from world_builder.agents.contracts import AgentError, CONFIG_SCHEMA, ROOT, strict_json, validate_schema
from world_builder.agents.runtime import write_json
from . import runner
from . import nature

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
    def __init__(self, root, config, *, execute=runner.execute, provider_factory=runner.provider_for, preferences_path=None, credential_store=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.config = deepcopy(config)
        self.preferences_path = Path(preferences_path) if preferences_path else None
        self.credential_store=credential_store
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

    def save_preferences(self, config):
        validate_schema(config, CONFIG_SCHEMA, "config.schema")
        if self.preferences_path is None:
            raise ServiceError(404, "preferences.disabled", "网页模式在浏览器中保存配置。")
        with self.lock:
            write_json(self.preferences_path, config)
            self.config = deepcopy(config)

    def _persist(self, job):
        write_json(self.root / job["id"] / "job.json", job)

    def credential_action(self,action,body):
        allowed={'endpoint','api_key'} if action=='save' else {'endpoint'}
        if not isinstance(body,dict) or set(body)!=allowed or not isinstance(body.get('endpoint'),str):
            raise ServiceError(400,'credential.fields','密钥设置字段无效。')
        endpoint=body['endpoint']
        try:
            url=urlsplit(endpoint)
            if len(endpoint)>2048 or url.scheme!='https' or not url.hostname or url.username or url.password or url.fragment:
                raise ValueError()
        except ValueError:raise ServiceError(400,'credential.endpoint','密钥只能绑定有效的HTTPS API地址。') from None
        with self.lock:
            store=self.credential_store
            if store is None or not store.supported:
                if action=='status':return {'supported':False,'saved':False}
                raise ServiceError(400,'credential.unsupported','仅Windows桌面支持加密记住密钥。')
            if action=='save':
                key=body['api_key']
                if not isinstance(key,str) or not 1<=len(key.strip())<=8192 or '\n' in key or '\r' in key:
                    raise ServiceError(400,'credential.key','请输入有效密钥，不能包含换行。')
                if endpoint!=self.config['endpoint']:raise ServiceError(409,'credential.config','请先保存对应API地址，再保存密钥。')
                store.save(endpoint,key.strip())
            elif action=='clear':store.clear(endpoint)
            return store.status(endpoint)

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
        allowed = {"mode", "prompt", "region_m", "seed", "minecraft", "unity", "config", "api_key", "replay_id", "pipeline", "source_id", "changes"}
        if set(body) - allowed or body.get("mode") not in {"api", "fixture", "replay", "adjust"}:
            raise ServiceError(400, "input.fields", "未知字段或运行模式。")
        if body.get('pipeline','legacy') not in ('legacy',nature.PROFILE):
            raise ServiceError(400,'input.pipeline','未知生成入口。')
        with self.lock:
            if any(j["status"] not in TERMINAL for j in self.jobs.values()):
                raise ServiceError(409, "job.busy", "已有运行进行中，请等待结束或取消。")
            mode = body["mode"]
            replay_path = None
            if mode == "replay":
                source = self._get(str(body.get("replay_id", "")))
                source_root = self.root / source["id"]
                if not (source_root / "output" / "calls").is_dir() and not (source.get('pipeline')==nature.PROFILE and source.get('source_mode')!='api'):
                    raise ServiceError(409, "replay.empty", "该运行没有可回放的调用记录。")
                spec = read_json(source_root / "input.json")
                config = read_json(source_root / "config.json")
                if spec is None or config is None:
                    raise ServiceError(409, "replay.metadata", "回放元数据不完整。")
                if spec.get('pipeline')==nature.PROFILE and spec.get('generation_context')!=nature.generation_context():
                    raise ServiceError(409,'replay.context','生成器版本或配方已变化，不能混用旧记录回放。旧结果仍保留。')
                spec.update(mode="replay", replay_id=source["id"])
                replay_path = source_root / "output"
            elif body.get('pipeline') == nature.PROFILE:
                if mode!='adjust' and any(k in body for k in ('changes','source_id')):
                    raise ServiceError(400,'input.fields','请通过受限调整操作提交changes与source_id。')
                config=deepcopy(body.get('config',nature.metadata()['default_config']))
                spec={'pipeline':nature.PROFILE,'profile_version':nature.VERSION,'mode':mode,'source_mode':mode,
                      'prompt':body.get('prompt',nature.PROMPT),'region_m':body.get('region_m',768),'seed':body.get('seed',46),
                      'minecraft':body.get('minecraft',False),'unity':body.get('unity',True),'generation_context':nature.generation_context()}
                if mode=='fixture':
                    if body.get('prompt',nature.PROMPT)!=nature.PROMPT:raise ServiceError(400,'fixture.fixed','离线山谷使用录制参数；新描述请用API模式。')
                    ref=nature.reference();spec.update(parameters=ref['parameters'],reference_provenance={k:v for k,v in ref.items() if k!='parameters'},prompt=nature.PROMPT)
                elif mode=='adjust':
                    source=self._get(str(body.get('source_id','')))
                    if source['status']!='succeeded' or source.get('pipeline')!=nature.PROFILE:
                        raise ServiceError(409,'adjust.source','只能调整本周山谷模式中已经成功的版本。')
                    parameters=read_json(self.root/source['id']/'output/accepted_parameters.json')
                    if parameters is None:raise ServiceError(409,'adjust.metadata','原版本参数缺失，不能猜测恢复。')
                    parameters,changes=nature.change_parameters(parameters,body.get('changes'))
                    spec.update(parameters=parameters,changes=changes,source_id=source['id'],prompt=source['prompt'])
            else:
                if mode=='adjust' or any(k in body for k in ('changes','source_id')):
                    raise ServiceError(400,'input.pipeline','受限参数调整只适用于本周山谷入口。')
                config = deepcopy(body.get("config", self.config))
                spec = {"mode": mode, "prompt": body.get("prompt", SAMPLE_PROMPT if mode == "fixture" else ""),
                        "region_m": body.get("region_m", 32 if mode == "fixture" else 128),
                        "seed": body.get("seed", 1), "minecraft": body.get("minecraft", True),
                        "unity": body.get("unity", True)}
            validate_schema(config, CONFIG_SCHEMA, "config.schema")
            is_nature=spec.get('pipeline')==nature.PROFILE
            if is_nature:
                config=nature.effective_config(config)
                if spec['region_m']!=768 or type(spec['region_m']) is not int or spec['seed']!=46 or type(spec['seed']) is not int:
                    raise ServiceError(400,'nature.fixed','本周山谷模式固定768米、布局种子46。')
                if spec['minecraft'] is not False or spec['unity'] is not True:
                    raise ServiceError(400,'nature.target','山谷模式本周仅支持WIR与Unity GLB，不支持Minecraft。')
                if config['limits']['max_sites']<64:
                    raise ServiceError(400,'nature.budget','山谷模式需要max_sites至少64；可在设置中选择DeepSeek官方预设。')
            if not isinstance(spec["prompt"], str) or not 1 <= len(spec["prompt"].strip()) <= 20000:
                raise ServiceError(400, "input.prompt", "场景描述须为 1—20000 字。")
            if not is_nature and (type(spec["region_m"]) is not int or not 32 <= spec["region_m"] <= 512 or spec["region_m"] % 16):
                raise ServiceError(400, "input.region", "边长须为 32—512 米且是 16 的倍数。")
            if type(spec["seed"]) is not int or not 0 <= spec["seed"] <= 2**53 - 1:
                raise ServiceError(400, "input.seed", "网页种子须为 0—9007199254740991 的整数。")
            if any(type(spec[k]) is not bool for k in ("minecraft", "unity")):
                raise ServiceError(400, "input.export", "导出选项必须是布尔值。")
            if not is_nature and mode == "fixture" and (spec["prompt"] != SAMPLE_PROMPT or spec["region_m"] != 32 or spec["seed"] != 1):
                raise ServiceError(400, "fixture.fixed", "人工样例仅用于固定 32 米、seed 1 的商铺与大厅场景。请切换 API 模式测试自己的描述。")
            key = body.get("api_key") or None
            if key is not None and (not isinstance(key, str) or len(key) > 8192 or "\n" in key or "\r" in key):
                raise ServiceError(400, "api.credential", "密钥格式无效。")
            if mode=='api' and key is None and self.credential_store is not None and self.credential_store.supported:
                key=self.credential_store.get(config['endpoint'])
            provider = self.provider_factory(mode, config, api_key=key, replay_path=replay_path)
            job_id = uuid.uuid4().hex
            job = {"id": job_id, "mode": mode, "prompt": spec["prompt"], "region_m": spec["region_m"],
                   "seed": spec["seed"], "status": "running", "phase": "planning", "created_at": now(),
                   "updated_at": now(), "result": None, "error": None, "replay_id": spec.get("replay_id")}
            if is_nature:job.update(pipeline=nature.PROFILE,source_id=spec.get('source_id'),source_mode=spec.get('source_mode',mode))
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
        if job.get('pipeline')==nature.PROFILE and job['status']=='succeeded':
            job['parameters']=read_json(output/'accepted_parameters.json')
            job['changes']=read_json(self.root/job_id/'input.json',{}).get('changes',{})
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
