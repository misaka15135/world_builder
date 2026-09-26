"""Compile a scene description into a validated brief (pipeline stage A)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from world_builder.planning import (FixtureBriefProvider, SceneError, compile_brief,
                                    compile_brief_with_provider, load_setting_pack)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="scene description, e.g. '河谷里的魔法城邦，要有城堡和冒险者工会'")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--setting", help="force a background id instead of detecting it from the prompt")
    parser.add_argument("--response-fixture", type=Path,
                        help="replay an accepted model response instead of the offline rule compiler")
    parser.add_argument("--settings-root", type=Path, default=None)
    parser.add_argument("--output", type=Path, help="write the brief JSON here instead of stdout only")
    args = parser.parse_args(argv)
    root = args.settings_root
    try:
        if args.response_fixture:
            if not args.setting:
                raise SceneError("brief.setting", "--response-fixture needs --setting")
            kwargs = {"root": root} if root else {}
            brief = compile_brief_with_provider(args.prompt, args.seed,
                                                FixtureBriefProvider(args.response_fixture), args.setting, **kwargs)
            pack = load_setting_pack(args.setting, root) if root else load_setting_pack(args.setting)
        elif args.setting:
            kwargs = {"root": root} if root else {}
            pack = load_setting_pack(args.setting, **kwargs)
            detected = compile_brief(args.prompt, args.seed, **kwargs)
            # Forcing a background keeps that background's requirements even
            # when the wording would have detected another one.
            brief = compile_brief(args.prompt, args.seed, **kwargs) if detected.setting == args.setting else None
            if brief is None:
                raise SceneError("brief.setting",
                                 f"prompt reads as {detected.setting!r}; rerun without --setting or reword it")
        else:
            kwargs = {"root": root} if root else {}
            brief = compile_brief(args.prompt, args.seed, **kwargs)
            pack = load_setting_pack(brief.setting, **kwargs)
    except SceneError as exc:
        print(json.dumps({"code": exc.code, "message": str(exc)}, ensure_ascii=False))
        return 1
    report = {
        "brief": brief.to_dict(),
        "brief_digest": brief.digest(),
        "setting": {"id": pack.id, "display_name": pack.display_name, "style_profile": pack.style_profile,
                    "catalogue": pack.summary_counts()},
        "effective_requirements": [landmark.to_dict() for landmark in brief.requirements(pack)],
        "not_designed_yet": sorted(entry.type for entry in pack.planned_entries
                                   if entry.type in {landmark.type for landmark in brief.requirements(pack)}),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report["brief"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
