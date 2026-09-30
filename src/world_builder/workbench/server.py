"""Loopback-only HTTP transport for the modular workbench."""
from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import secrets
import shutil
from urllib.parse import parse_qs, urlsplit
import webbrowser

from world_builder.agents.contracts import AgentError, CONFIG_SCHEMA, ROOT, STAGES, canonical, response_schema, strict_json, validate_schema
from world_builder.agents.providers import load_config
from .jobs import JobService, SAMPLE_PROMPT, ServiceError


class RootLock:
    """OS lock prevents two local servers from recovering each other's jobs."""
    def __init__(self, root):
        Path(root).mkdir(parents=True, exist_ok=True)
        self.stream = (Path(root) / ".server.lock").open("a+b")
        self.stream.seek(0)
        self.stream.write(b"0")
        self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise RuntimeError("此运行目录已有测试台服务。请使用现有服务或更换 --runs 目录。") from None

    def close(self):
        self.stream.close()


class WorkbenchServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, service, web_root=ROOT / "web"):
        self.service, self.web_root = service, Path(web_root).resolve()
        self.token = secrets.token_urlsafe(32)
        super().__init__(address, Handler)

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.server_port}"


class Handler(BaseHTTPRequestHandler):
    server_version = "WorldBuilder/0.1"

    def log_message(self, format, *args):
        pass  # Never log request bodies, credentials or user descriptions.

    def headers_for(self, status, length, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")

    def json(self, status, data):
        payload = canonical(data)
        self.headers_for(status, len(payload), "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(payload)

    def file(self, path, *, download=False):
        content_type = {".js": "text/javascript", ".css": "text/css", ".html": "text/html",
                        ".json": "application/json", ".glb": "model/gltf-binary", ".svg": "image/svg+xml"}.get(path.suffix)
        self.headers_for(200, path.stat().st_size, content_type or "application/octet-stream")
        if download:
            # All exported filenames are compiler-generated ASCII identifiers.
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.end_headers()
        with path.open("rb") as stream:
            shutil.copyfileobj(stream, self.wfile)

    def dispatch(self, write=False):
        try:
            allowed_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in allowed_hosts:
                raise ServiceError(403, "http.host", "仅支持本机访问。")
            if write:
                origin = self.headers.get("Origin")
                if origin is not None and origin not in {"http://" + h for h in allowed_hosts}:
                    raise ServiceError(403, "http.origin", "拒绝跨来源写入。")
                if not hmac.compare_digest(self.headers.get("X-Workbench-Token", ""), self.server.token):
                    raise ServiceError(403, "http.session", "页面会话已失效，请刷新。")
                if self.headers.get_content_type() != "application/json":
                    raise ServiceError(415, "http.content_type", "请发送 application/json。")
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    raise ServiceError(400, "http.length", "无效请求长度。") from None
                if not 0 < length <= 262144:
                    raise ServiceError(413, "http.size", "请求大小须为 1—262144 字节。")
                body = strict_json(self.rfile.read(length))
            else:
                body = None
            url = urlsplit(self.path)
            parts = url.path.strip("/").split("/")
            query = parse_qs(url.query)
            svc = self.server.service
            if parts[:2] != ["api", "v1"]:
                if write:
                    raise ServiceError(404, "http.route", "接口不存在。")
                relative = url.path.lstrip("/") or "index.html"
                path = (self.server.web_root / relative).resolve()
                if not path.is_relative_to(self.server.web_root) or not path.is_file() or path.suffix not in {".html", ".js", ".css", ".svg"}:
                    raise ServiceError(404, "http.asset", "页面资源不存在。")
                return self.file(path)
            route = parts[2:]
            if route == ["bootstrap"] and not write:
                return self.json(200, {"api_version": "1", "session_token": self.server.token,
                    "settings_persistence": "application" if svc.preferences_path else "browser",
                    "config": svc.config, "sample": {"prompt": SAMPLE_PROMPT, "region_m": 32, "seed": 1},
                    "credential_available": bool(os.environ.get(svc.config["api_key_env"], "")),
                    "skills": [{"stage": s, "text": (ROOT / f"skills/world-agent-{s.lower()}/SKILL.md").read_text("utf-8")
                                + ("\n\n" + (ROOT / "skills/world-agent-e/references/design-principles.md").read_text("utf-8") if s == "E" else "")}
                               for s in STAGES]})
            if route == ["config", "validate"] and write:
                validate_schema(body, CONFIG_SCHEMA, "config.schema")
                return self.json(200, {"valid": True})
            if route == ["preferences"] and write:
                svc.save_preferences(body)
                return self.json(200, {"saved": True})
            if len(route) == 2 and route[0] == "contracts" and route[1] in STAGES and not write:
                return self.json(200, response_schema(route[1]))
            if route == ["jobs"]:
                return self.json(202, svc.create(body)) if write else self.json(200, {"jobs": svc.list()})
            if len(route) >= 2 and route[0] == "jobs":
                job_id = route[1]
                if len(route) == 2 and not write:
                    return self.json(200, svc.detail(job_id))
                if route[2:] == ["cancel"] and write:
                    return self.json(200, svc.cancel(job_id))
                if route[2:] in (["file"], ["document"], ["scene"]) and not write:
                    relative = "repository/scene.world.json" if route[2] == "scene" else query.get("path", [""])[0]
                    path = svc.resource_path(job_id, relative)
                    if route[2] == "document":
                        if path.suffix not in {".json", ".jsonl"} or path.stat().st_size > 2_000_000:
                            raise ServiceError(413, "document.size", "仅预览 2 MB 以内的 JSON / JSONL，其余请下载。")
                        return self.json(200, {"path": relative, "text": path.read_text("utf-8")})
                    return self.file(path, download=route[2] == "file")
            raise ServiceError(404, "http.route", "接口不存在。")
        except ServiceError as exc:
            self.json(exc.status, {"error": {"code": exc.code, "message": str(exc)}})
        except (AgentError, ValueError) as exc:
            self.json(400, {"error": {"code": getattr(exc, "code", "input.invalid"), "message": str(exc)}})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            self.json(500, {"error": {"code": "server.error", "message": "本地服务处理失败，请检查运行目录或重启服务。"}})

    def do_GET(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch(write=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="World Builder 本地网页测试台")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--runs", type=Path, default=ROOT / "artifacts/agent-runs/workbench")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / ("agents.local.json" if (ROOT / "config/agents.local.json").exists() else "agents.example.json"))
    parser.add_argument("--open", action="store_true", help="打开默认浏览器")
    args = parser.parse_args(argv)
    lock = service = server = None
    try:
        config = load_config(args.config)
        lock = RootLock(args.runs)
        service = JobService(args.runs, config)
        server = WorkbenchServer(("127.0.0.1", args.port), service)
        print(f"World Builder: {server.origin}\n按 Ctrl+C 停止服务。运行保存在 {args.runs}", flush=True)
        if args.open:
            webbrowser.open(server.origin)
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        if server:
            server.server_close()
        if service:
            service.close()
        if lock:
            lock.close()
    return 0
