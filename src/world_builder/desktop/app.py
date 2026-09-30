"""Native WebView2 host with owned HTTP lifecycle and persistent user data."""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from threading import Event, Thread
import time

from world_builder.agents.contracts import ROOT
from world_builder.agents.providers import load_config
from world_builder.agents.runtime import write_json
from world_builder.workbench.jobs import JobService, TERMINAL
from world_builder.workbench.server import RootLock, WorkbenchServer
from . import VERSION


def user_directory():
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "WorldBuilder"


class DesktopSession:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RootLock(self.root)
        self.service = self.server = self.thread = None
        self.closed = False
        try:
            path = self.root / "preferences.json"
            config = load_config(path if path.exists() else ROOT / "config/agents.example.json")
            self.service = JobService(self.root / "runs", config, preferences_path=path)
            self.server = WorkbenchServer(("127.0.0.1", 0), self.service)
            self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": .2}, daemon=True)
            self.thread.start()
            write_json(self.root / "session.json", {"pid": os.getpid(), "origin": self.server.origin,
                       "version": VERSION, "started_at": datetime.now(timezone.utc).isoformat()})
        except Exception:
            self.close()
            raise

    def active(self):
        return any(job["status"] not in TERMINAL for job in self.service.list())

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.service:
                self.service.close()
            if self.server:
                if self.thread and self.thread.is_alive():
                    self.server.shutdown()
                    self.thread.join(3)
                self.server.server_close()
        finally:
            self.lock.close()


def self_test(session):
    """Explicit packaging check: actual bundled fixture, replay and exports."""
    results = []
    for body in ({"mode": "fixture"}, {"mode": "replay"}):
        if results:
            body["replay_id"] = results[0]["id"]
        job = session.service.create(body)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            detail = session.service.detail(job["id"])
            if detail["status"] in TERMINAL:
                break
            time.sleep(.05)
        if detail["status"] != "succeeded":
            raise RuntimeError(f"Bundled self-test failed: {detail.get('error')}")
        results.append(detail)
    if results[0]["result"]["worldpkg_sha256"] != results[1]["result"]["worldpkg_sha256"]:
        raise RuntimeError("Replay world package differs")
    report = {"version": VERSION, "status": "pass", "resource_root": str(ROOT),
              "runs": [{"id": job["id"], "result": job["result"]} for job in results]}
    write_json(session.root / "self-test.json", report)


def show_error(message):
    ctypes.windll.user32.MessageBoxW(None, message, "World Builder · 启动失败", 0x10)


def main(argv=None):
    parser = argparse.ArgumentParser(description="World Builder desktop application")
    parser.add_argument("--data-dir", type=Path, default=user_directory())
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    args.data_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=args.data_dir / "desktop.log", level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    session = None
    try:
        session = DesktopSession(args.data_dir)
        if args.self_test:
            self_test(session)
            return 0
        import webview
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.settings["ALLOW_FILE_URLS"] = False
        window = webview.create_window("World Builder · 世界构建器", session.server.origin,
                                       width=1440, height=960, min_size=(960, 700),
                                       text_select=True, background_color="#f5f5ee")
        closing = Event()
        finished = Event()

        def finish_close():
            session.close()
            finished.set()
            window.destroy()

        def on_closing():
            if finished.is_set() or not session.active():
                return True
            if not closing.is_set():
                closing.set()
                window.set_title("World Builder · 正在停止任务并保存记录…")
                Thread(target=finish_close, daemon=True).start()
            return False

        window.events.closing += on_closing
        webview.start(gui="edgechromium", private_mode=False,
                      storage_path=str(args.data_dir / "webview"),
                      icon=str(ROOT / "desktop/world-builder.ico"))
        return 0
    except Exception as exc:
        logging.exception("Desktop startup or execution failed")
        if args.self_test:
            write_json(args.data_dir / "self-test.json", {"status": "failed", "error": str(exc)})
        else:
            show_error(f"{exc}\n\n请确认本机已安装 Microsoft Edge WebView2 Runtime。\n日志：{args.data_dir / 'desktop.log'}")
        return 1
    finally:
        if session:
            session.close()
