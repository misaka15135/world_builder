"""Export a verified WIR 512 m city package as chunked Sponge v3 schematics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from world_builder.adapters.minecraft.city import DEFAULT_DATA_VERSION, export_city
from world_builder.storage.worldpkg import read_worldpkg


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-version", type=int, default=DEFAULT_DATA_VERSION)
    parser.add_argument("--interiors", action="store_true",
                        help="materialize the five generated two-storey interiors as block shells")
    args = parser.parse_args()
    package, _ = read_worldpkg(args.source)
    print(json.dumps(export_city(package, args.output,
                                 include_interiors=args.interiors,
                                 data_version=args.data_version),
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
