"""Export the frozen hand-authored two-storey WIR sample to Sponge schematic v3."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from world_builder.wir.validator import PackageValidationError

from .sample import SampleExportError, export_sample


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("examples/two_storey_building.world.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-version", type=int, required=True,
                        help="Java DataVersion from the target installation; not inferred by this adapter")
    args = parser.parse_args(argv)
    try:
        package = json.loads(args.source.read_text(encoding="utf-8"))
        result = export_sample(package, args.output, data_version=args.data_version)
    except (OSError, ValueError, PackageValidationError) as exc:
        print(json.dumps({"code": getattr(exc, "code", "target.sample_error"), "message": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
