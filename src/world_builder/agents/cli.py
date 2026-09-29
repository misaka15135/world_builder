"""CLI for API planning, explicit fixtures, or hash-bound offline replay."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .compiler import save_world
from .contracts import ROOT, AgentError
from .providers import APIProvider, FixtureProvider, ReplayProvider, load_config
from .runtime import Supervisor, write_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "agents.example.json")
    parser.add_argument("--output", type=Path, required=True, help="new run directory; existing paths are never overwritten")
    parser.add_argument("--region-m", type=int, default=128)
    parser.add_argument("--seed", type=int, default=1)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fixtures", type=Path, help="explicit synthetic responses; no model-quality claim")
    mode.add_argument("--replay", type=Path, help="replay a previous run's exact requests and responses")
    parser.add_argument("--minecraft", action="store_true")
    parser.add_argument("--unity", action="store_true")
    args = parser.parse_args(argv)
    supervisor = None
    try:
        config = load_config(args.config)
        provider = (FixtureProvider(args.fixtures) if args.fixtures else ReplayProvider(args.replay)
                    if args.replay else APIProvider(config))
        supervisor = Supervisor(provider, config, args.output, region_m=args.region_m, seed=args.seed)
        accepted = supervisor.run(args.prompt)
        supervisor.checkpoint()
        result = save_world(accepted, args.output, config["limits"], minecraft=args.minecraft, unity=args.unity)
        result.update(supervisor.usage())
        result["mode"] = "synthetic_fixture" if args.fixtures else "replay" if args.replay else "api"
        write_json(args.output / "result.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (AgentError, ValueError, OSError, KeyboardInterrupt) as exc:
        result = {"status": "failed", "code": getattr(exc, "code", "execution.error"), "message": str(exc),
                  "feasibility": "unknown"}
        if supervisor is not None:
            result.update(supervisor.usage())
            write_json(args.output / "result.json", result)
        print(json.dumps(result, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
