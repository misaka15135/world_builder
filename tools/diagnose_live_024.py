#!/usr/bin/env python3
"""Retry one recorded A-stage request solely to diagnose a DeepSeek HTTP 400."""
from __future__ import annotations

import getpass
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from world_builder.agents.contracts import AgentError  # noqa: E402
from world_builder.agents.providers import APIProvider, load_config  # noqa: E402

CASE = ROOT / "artifacts/agent-runs/live-024-deepseek-v1/single_storey"
REQUEST_ID = "08af1d72e836f834f2f9c1ede0b1810d1273ae781f8c240af7e347d85ee3a028"
SOURCE = CASE / "calls" / REQUEST_ID / "request.json"
OUTPUT = ROOT / "artifacts/agent-runs/live-024-deepseek-v1/diagnostic-A"


def main() -> int:
    if OUTPUT.exists():
        raise SystemExit("Diagnostic output already exists; refusing to overwrite it")
    request_bytes = SOURCE.read_bytes()
    request = json.loads(request_bytes)
    config = load_config(ROOT / "config/agents.deepseek-024.json")
    key_name = config["api_key_env"]
    entered_key = not bool(os.environ.get(key_name))
    if entered_key:
        key = getpass.getpass("DeepSeek API key (input hidden): ").strip()
        if not key:
            raise SystemExit("API key is required")
        os.environ[key_name] = key
        del key
    started = time.monotonic()
    report = {"kind": "out_of_batch_http_diagnostic", "stage": "A",
              "original_request_sha256": "sha256:" + hashlib.sha256(request_bytes).hexdigest(),
              "model_requested": config["model"], "endpoint": config["endpoint"],
              "attempt_count": 1}
    try:
        try:
            completion = APIProvider(config).complete(request, timeout_s=config["limits"]["timeout_s"])
        except AgentError as exc:
            report.update(status="failed", error_code=exc.code, error_message=str(exc))
        else:
            OUTPUT.mkdir(parents=True)
            (OUTPUT / "response.json").write_bytes(completion.raw)
            report.update(status="completed", model_returned=completion.model,
                          input_tokens=completion.input_tokens,
                          output_tokens=completion.output_tokens,
                          response_sha256="sha256:" + hashlib.sha256(completion.raw).hexdigest())
    finally:
        if entered_key:
            os.environ.pop(key_name, None)
    report["elapsed_s"] = round(time.monotonic() - started, 3)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "diagnostic.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
