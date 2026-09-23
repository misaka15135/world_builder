from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .validator import PackageValidationError, load_and_validate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate WIR 0.1 package snapshots")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--schema", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    failed = False
    for path in args.paths:
        try:
            package = load_and_validate(path, args.schema)
        except (OSError, ValueError, RuntimeError, PackageValidationError) as exc:
            failed = True
            print(f"FAIL {path}\n{exc}", file=sys.stderr)
        else:
            print(f"OK   {path} records={len(package['records'])} revision={package['manifest']['revision_id']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
