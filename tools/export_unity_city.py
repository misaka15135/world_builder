"""Export a verified WIR city worldpkg as a Unity static GLB scene package."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from world_builder.adapters.unity.city import export_city
from world_builder.storage.worldpkg import read_worldpkg


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package, _ = read_worldpkg(args.source)
    print(json.dumps(export_city(package, args.output), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
