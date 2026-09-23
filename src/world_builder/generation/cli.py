from __future__ import annotations

import argparse
import json
import os
import signal
import tempfile
from pathlib import Path

from world_builder.storage.repository import Repository
from .pipeline import generate, semantic_hash
from .spec import Budget, PilotSpec, canonical


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".snapshot-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate/resume a bounded WIR pilot; not the full 006 city acceptance")
    parser.add_argument("--output", type=Path, required=True, help="SQLite repository and resources directory")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--scenario", choices=["riverside", "hillside", "dense"], default="riverside")
    parser.add_argument("--buildings", type=int, default=6)
    parser.add_argument("--interiors", type=int, default=2)
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--max-candidates", type=int, default=3, help="per-stage candidate cap, including the initial candidate")
    parser.add_argument("--layout-profile", choices=["standard", "compact"], default="standard")
    parser.add_argument("--lock-stair-void", action="store_true", help="protect the initial building stair reservation")
    args = parser.parse_args(argv)
    try:
        spec = PilotSpec(seed=args.seed, scenario=args.scenario, building_count=args.buildings, interior_count=args.interiors,
                         layout_profile=args.layout_profile, lock_stair_void=args.lock_stair_void)
        budget = Budget(wall_time_ms=args.timeout_ms, max_candidates=args.max_candidates)
    except ValueError as exc:
        parser.error(str(exc))
    repository = Repository(args.output)
    interrupted = False

    def cancel(signum, frame):
        nonlocal interrupted
        interrupted = True

    previous_handler = signal.signal(signal.SIGINT, cancel)
    try:
        result = generate(spec, repository, budget, cancelled=lambda: interrupted)
    finally:
        signal.signal(signal.SIGINT, previous_handler)
    report = result.to_dict()
    if result.revision_id:
        package = repository.load(spec.world_id, result.revision_id)
        snapshot = repository.root / (spec.world_id + ".world.json")
        atomic_json(snapshot, package)
        report["snapshot"] = str(snapshot)
        report["semantic_hash"] = semantic_hash(package)
    atomic_json(repository.root / (spec.world_id + ".run.json"), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if result.termination_reason == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
