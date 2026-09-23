"""Command-line entrypoint for WIR exchange archives."""
from __future__ import annotations

import argparse
import json

from .repository import Repository, StoreError
from .worldpkg import export_worldpkg, import_worldpkg, read_worldpkg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--repo", required=True)
    export.add_argument("--world-id", required=True)
    export.add_argument("--revision-id")
    export.add_argument("--output", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("path")
    imported = commands.add_parser("import")
    imported.add_argument("path")
    imported.add_argument("--repo", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            checksum = export_worldpkg(Repository(args.repo), args.world_id, args.output, args.revision_id)
            result = {"path": args.output, "sha256": checksum}
        elif args.command == "verify":
            package, resources = read_worldpkg(args.path)
            result = {"world_id": package["manifest"]["world_id"], "revision_id": package["manifest"]["revision_id"],
                      "records": len(package["records"]), "resources": len(resources)}
        else:
            world_id, revision_id = import_worldpkg(Repository(args.repo), args.path)
            result = {"world_id": world_id, "revision_id": revision_id}
    except (OSError, ValueError, StoreError) as exc:
        print(json.dumps({"code": getattr(exc, "code", "resource.package_error"), "message": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0
