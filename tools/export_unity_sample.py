"""Export the frozen two-storey sample as a Unity-targeted GLB experiment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from world_builder.adapters.unity.sample import export_sample


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("examples/two_storey_building.world.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = export_sample(json.loads(args.source.read_text(encoding="utf-8")), args.output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
