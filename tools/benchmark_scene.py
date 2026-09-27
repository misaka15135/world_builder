#!/usr/bin/env python3
"""Run the preregistered scene cases end to end, one fresh process per case.

The registry is frozen before the run (see `benchmarks/scene_cases_v1.json`) and
is not filtered afterwards: a case that fails keeps its SceneError code in the
report. Each case runs in its own process so the peak working set is the case's
own, and the whole batch is offline — no model calls are made.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from world_builder.adapters.minecraft.city import export_city
from world_builder.adapters.minecraft.scene import project_for_minecraft
from world_builder.planning import (SceneError, assemble_scene, compile_brief, load_designs,
                                    load_setting_pack, plan_siting, plan_terrain, validate_scene)
from world_builder.planning.designer import design_building


def peak_working_set() -> int:
    """Peak RSS of this process; Windows needs the psapi counter."""
    if sys.platform == "win32":
        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t) for name in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                    "PagefileUsage", "PeakPagefileUsage")]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(counters.PeakWorkingSetSize)
    import resource
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def run_case(case: dict, registry: dict, output: Path) -> dict:
    started = time.perf_counter()
    record = {"id": case["id"], "setting": case["setting"], "seed": case["seed"]}
    try:
        prompt = registry["settings"][case["setting"]]
        pack = load_setting_pack(case["setting"])
        brief = compile_brief(prompt, seed=case["seed"])
        terrain = plan_terrain(case["setting"], seed=case["seed"],
                               region_m=registry["region_m"], spacing_m=registry["spacing_m"])
        siting = plan_siting(brief, pack, terrain)
        templates = load_designs(case["setting"])
        designs, skipped = [], set()
        for site in siting.sites:
            template = templates.get(site.type)
            if template is None:
                skipped.add(site.type)
                continue
            block = siting.block(site.block_id)
            side = "south" if abs(block.centre[1] - site.y0) < abs(block.centre[1] - site.y1) else "north"
            designs.append(design_building(site, pack.entry(site.type), pack, template,
                                           entry_side=side, seed=case["seed"]))
        designs = tuple(designs)
        package = assemble_scene(brief, pack, terrain, siting, designs)
        report = validate_scene(package, terrain, siting, designs)
        # The blocks are measured, not kept: a per-run scratch directory keeps
        # re-runs from colliding with earlier ones (a FileExistsError polluted
        # the first batch).
        with tempfile.TemporaryDirectory(prefix=f"scene-{case['id']}-") as scratch:
            export = export_city(project_for_minecraft(package), Path(scratch) / case["id"],
                                 include_interiors=True)
        record |= {
            "state": "pass" if report["state"] == "pass" else "fail",
            "validation": report["state"],
            "world_id": package["manifest"]["world_id"],
            "revision_id": package["manifest"]["revision_id"],
            "record_count": report["record_count"],
            "designs": len(designs),
            "skipped_types": sorted(skipped),
            "chunks": export["chunk_count"],
            "boxes": export["box_count"],
            "non_air_blocks": export["non_air_blocks"],
            "model_calls": brief.model_calls,
        }
    except SceneError as exc:
        record |= {"state": "fail", "failure_code": exc.code, "failure_message": str(exc)}
    except Exception as exc:  # noqa: BLE001 - the batch must preserve every failure
        record |= {"state": "fail", "failure_code": type(exc).__name__, "failure_message": str(exc)}
    record["seconds"] = round(time.perf_counter() - started, 3)
    record["peak_working_set_bytes"] = peak_working_set()
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("benchmarks/scene_cases_v1.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/scene-benchmark-v1"))
    parser.add_argument("--case", help="run a single case id in this process (worker mode)")
    args = parser.parse_args(argv)
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    if args.case:
        case = next(case for case in registry["cases"] if case["id"] == args.case)
        print(json.dumps(run_case(case, registry, args.output), ensure_ascii=False))
        return 0
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for case in registry["cases"]:
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--registry", str(args.registry),
             "--output", str(args.output), "--case", case["id"]],
            capture_output=True, text=True)
        payload = None
        for line in reversed(completed.stdout.splitlines()):
            if line.startswith("{"):
                payload = json.loads(line)
                break
        if payload is None:
            payload = {"id": case["id"], "setting": case["setting"], "seed": case["seed"],
                       "state": "fail", "failure_code": "worker.crash",
                       "failure_message": (completed.stderr or completed.stdout)[-400:]}
        results.append(payload)
        print(f"  {payload['id']:14s} {payload['state']:4s} {payload.get('seconds', 0):8.1f}s "
              f"{payload.get('designs', '-')} designs "
              f"{payload.get('failure_code', '')}")
    passed = [r for r in results if r["state"] == "pass"]
    seconds = [r["seconds"] for r in results]
    peaks = [r["peak_working_set_bytes"] for r in results]
    summary = {
        "cases": len(results),
        "passed": len(passed),
        "success_rate": round(len(passed) / len(results), 3),
        "failure_reasons": sorted({r.get("failure_code") for r in results if r["state"] != "pass"}),
        "seconds_total": round(sum(seconds), 1),
        "seconds_mean": round(statistics.mean(seconds), 2),
        "seconds_max": round(max(seconds), 2),
        "peak_working_set_max_mb": round(max(peaks) / 1024 / 1024, 1),
        "peak_working_set_mean_mb": round(statistics.mean(peaks) / 1024 / 1024, 1),
        "model_calls": sum(r.get("model_calls", 0) for r in results),
    }
    (args.output / "report.json").write_text(
        json.dumps({"registry": registry, "summary": summary, "results": results},
                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0 if len(passed) == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
