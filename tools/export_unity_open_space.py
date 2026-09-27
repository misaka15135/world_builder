"""Export one scene-pipeline open space to a bounded Unity GLB sample."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from world_builder.adapters.unity.scene import export_open_space


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package = json.loads(args.source.read_text(encoding="utf-8"))
    result = export_open_space(package, args.source_id, args.output)
    print(json.dumps({"source_id": result["source_id"], "piece_count": result["piece_count"],
                      "source_revision_id": result["source_revision_id"],
                      "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
