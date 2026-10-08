"""Export the versioned timber street-house study to both installed targets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from world_builder.samples.street_house import export_study


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = export_study(args.output)
    print(json.dumps({"output": str(args.output), "geometry_sha256": manifest["geometry_sha256"],
                      "piece_count": manifest["piece_count"],
                      "non_air_blocks": manifest["non_air_blocks"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
