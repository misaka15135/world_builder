#!/usr/bin/env python3
"""Run one pre-registered 024 DeepSeek case with an interactively entered key."""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from world_builder.agents.cli import main as run_agent  # noqa: E402
from world_builder.agents.providers import load_config  # noqa: E402
from world_builder.storage.worldpkg import read_worldpkg  # noqa: E402
from world_builder.wir.validator import load_and_validate  # noqa: E402

REGISTER = ROOT / "benchmarks/agent_live_024_deepseek_v1.json"


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def verify_replay(original: Path, replay: Path) -> dict:
    source = json.loads((original / "result.json").read_text(encoding="utf-8"))
    reproduced = json.loads((replay / "result.json").read_text(encoding="utf-8"))
    package, _ = read_worldpkg(original / "scene.worldpkg")
    source_matches_archive = package == load_and_validate(original / "repository/scene.world.json")
    names = ["scene.worldpkg", "unity/scene.glb"]
    names.extend(str(path.relative_to(original)).replace("\\", "/")
                 for path in sorted((original / "minecraft").glob("*.schem")))
    same_files = all((replay / name).is_file() and sha256(original / name) == sha256(replay / name)
                     for name in names)
    checks = {
        "source_mode_api": source.get("mode") == "api" and source.get("network_calls", 0) > 0,
        "replay_offline": reproduced.get("mode") == "replay" and reproduced.get("network_calls") == 0,
        "source_package_valid": source_matches_archive,
        "same_revision": source.get("revision_id") == reproduced.get("revision_id"),
        "same_export_files": same_files,
    }
    report = {"status": "pass" if all(checks.values()) else "fail", "checks": checks,
              "compared_paths": names}
    (original / "replay_validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate setup without API access")
    parser.add_argument("--case", help="one case ID from the registered batch")
    parser.add_argument("--replay", action="store_true", help="replay a completed API case offline")
    parser.add_argument("--key-file", type=Path,
                        help="read only the first line locally; never print or copy the key")
    args = parser.parse_args()

    batch = json.loads(REGISTER.read_text(encoding="utf-8"))
    cases = {item["id"]: item for item in batch["cases"]}
    config_path = ROOT / batch["config"]
    config = load_config(config_path)
    if len(cases) != batch["sample_count"] or len(cases) != len(batch["cases"]):
        parser.error("registered sample count or IDs do not match")
    if config["endpoint"] != "https://api.deepseek.com/chat/completions" or config["model"] != "deepseek-flash":
        parser.error("this registered batch requires the official DeepSeek Flash endpoint and model")
    if config["token_parameter"] != "max_tokens" or config["response_format"] != "json_object":
        parser.error("DeepSeek wire configuration differs from the registered batch")
    if args.check:
        print(json.dumps({"status": "ready", "batch_id": batch["batch_id"],
                          "case_ids": list(cases), "model": config["model"],
                          "max_calls_per_case": config["limits"]["max_calls"],
                          "key_present": bool(os.environ.get(config["api_key_env"]))}, ensure_ascii=False))
        return 0
    if args.case not in cases:
        parser.error("--case must be one of: " + ", ".join(cases))

    original = ROOT / "artifacts" / "agent-runs" / "live-024-deepseek-v1" / args.case
    output = original.with_name(original.name + "-replay") if args.replay else original
    if output.exists():
        parser.error(f"output already exists; never overwrite a registered result: {output}")
    if args.replay:
        if not (original / "scene.worldpkg").is_file():
            parser.error("replay requires a completed original API case")
        case = cases[args.case]
        command = ["--prompt", case["prompt"], "--config", str(config_path),
                   "--output", str(output), "--region-m", str(case["region_m"]),
                   "--seed", str(case["seed"]), "--minecraft", "--unity",
                   "--replay", str(original)]
        exit_code = run_agent(command)
        if exit_code:
            return exit_code
        report = verify_replay(original, output)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "pass" else 1
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()

    key_name = config["api_key_env"]
    entered_key = not bool(os.environ.get(key_name))
    if entered_key:
        if args.key_file:
            with args.key_file.open("rb") as stream:
                encoding = "utf-16" if stream.read(2) in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
            with args.key_file.open("r", encoding=encoding) as stream:
                key = stream.readline().strip()
        else:
            key = getpass.getpass("DeepSeek API key (input hidden, held only in this process): ").strip()
        if not key:
            parser.error("API key is required")
        os.environ[key_name] = key
        del key

    case = cases[args.case]
    command = ["--prompt", case["prompt"], "--config", str(config_path),
               "--output", str(output), "--region-m", str(case["region_m"]),
               "--seed", str(case["seed"]), "--minecraft", "--unity"]
    try:
        exit_code = run_agent(command)
        if output.exists():
            context = {"batch_id": batch["batch_id"], "case_id": args.case,
                       "prereg_sha256": sha256(REGISTER), "config_sha256": sha256(config_path),
                       "checkout_commit": revision, "endpoint": config["endpoint"],
                       "model": config["model"], "program_exit_code": exit_code}
            (output / "evaluation_context.json").write_text(
                json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return exit_code
    finally:
        if entered_key:
            os.environ.pop(key_name, None)


if __name__ == "__main__":
    raise SystemExit(main())
