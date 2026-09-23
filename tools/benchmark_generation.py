#!/usr/bin/env python3
"""Run every preregistered pilot case in a fresh process; preserve failures."""
from __future__ import annotations

import argparse
import ctypes
import importlib.metadata
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

from world_builder.generation import GENERATOR_VERSION
from world_builder.generation.cli import atomic_json
from world_builder.generation.pipeline import generate, semantic_hash
from world_builder.generation.spec import Budget, PilotSpec, digest
from world_builder.storage.repository import Repository


def peak_working_set() -> int:
    if sys.platform == "win32":
        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return counters.PeakWorkingSetSize
    import resource
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def worker(case: dict, output: Path) -> dict:
    spec = PilotSpec(**case["spec"])
    repository = Repository(output)
    start = time.perf_counter()
    result = generate(spec, repository, Budget(**case["budget"]))
    report = result.to_dict()
    report.update({"case_id": case["id"], "scenario": spec.scenario, "wall_time_ms": round((time.perf_counter()-start)*1000, 3),
                   "peak_working_set_bytes": peak_working_set(), "model_calls": 0})
    if result.revision_id:
        package = repository.load(spec.world_id)
        report["semantic_hash"] = semantic_hash(package)
        report["entities"] = sum(r["record_type"] == "entity" for r in package["records"])
        report["record_count"] = len(package["records"])
        report["resource_bytes"] = sum(p.stat().st_size for p in (repository.root / "assets/sha256").iterdir())
        atomic_json(output / "snapshot.world.json", package)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("benchmarks/pilot_cases_v3.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(json.loads(args.worker), args.output)))
        return 0
    registration = json.loads(args.cases.read_text(encoding="utf-8"))
    if registration["generator_version"] != GENERATOR_VERSION:
        parser.error("preregistered generator version does not match the implementation")
    if args.output.exists():
        parser.error("benchmark output must be new; existing results are never overwritten")
    args.output.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    sources = sorted((root / "src/world_builder/generation").glob("*.py")) + sorted((root / "src/world_builder/storage").glob("*.py"))
    report = {"scope": "128m_pilot_not_006_city_acceptance", "registration_hash": digest(registration),
              "implementation_hash": digest({p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in sources}),
              "generator_version": GENERATOR_VERSION,
              "environment": {"hostname": platform.node(), "platform": platform.platform(), "python": sys.version,
                  "jsonschema": importlib.metadata.version("jsonschema"), "pytest": importlib.metadata.version("pytest")},
              "cases": []}
    atomic_json(args.output / "registration.json", registration)
    for case in registration["cases"]:
        try:
            completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", json.dumps(case),
                                        "--output", str(args.output / case["id"])], capture_output=True, text=True, timeout=90)
            if completed.returncode:
                raise RuntimeError(completed.stderr[-4000:])
            entry = json.loads(completed.stdout)
        except Exception as exc:
            entry = {"case_id": case["id"], "scenario": case["spec"]["scenario"], "termination_reason": "error", "feasibility": "unknown", "message": str(exc)}
        report["cases"].append(entry)
        atomic_json(args.output / "report.json", report)
        print(f"{case['id']}: {entry['termination_reason']}", flush=True)
    passed = [c for c in report["cases"] if c["termination_reason"] == "completed" and c["feasibility"] == "feasible"]
    report["summary"] = {"total": len(registration["cases"]), "completed": len(report["cases"]), "succeeded": len(passed),
        "first_attempt_passed": sum(all(s["attempts"] == 1 for s in c["stages"]) for c in passed),
        "by_scenario": {scenario: sum(c["scenario"] == scenario for c in passed) for scenario in ("riverside", "hillside", "dense")},
        "full_city_acceptance": False}
    atomic_json(args.output / "report.json", report)
    print(json.dumps(report["summary"], indent=2))
    return 0 if len(passed) == len(registration["cases"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
