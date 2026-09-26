"""Plan districts, ownership, the road skeleton and building envelopes (stage D)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from world_builder.planning import (SceneError, brief_from_dict, compile_brief, load_setting_pack,
                                    plan_siting, plan_terrain, render_preview, validate_siting)


def render_blocks(plan, width: int = 60) -> str:
    """A block map: one character per use, domains marked in the second row."""
    glyph = {"civic": "C", "market": "M", "residential": "r", "craft": "w", "green": "g",
             "industrial": "I", "harbour": "H"}
    step = max(1.0, plan.region_m / width)
    lines = []
    for row in range(int(plan.region_m // step)):
        y = (row + 0.5) * step
        line = []
        for column in range(int(plan.region_m // step)):
            x = (column + 0.5) * step
            block = next((item for item in plan.blocks
                          if item.x0 <= x < item.x1 and item.y0 <= y < item.y1), None)
            site = next((item for item in plan.sites if item.x0 <= x < item.x1 and item.y0 <= y < item.y1), None)
            line.append("*" if site else (glyph.get(block.use, "?") if block else " "))
        # Arterials drawn over the block fabric.
        for road in plan.roads:
            if road.kind != "arterial":
                continue
            for index in range(len(road.points) - 1):
                ax, ay = road.points[index]
                bx, by = road.points[index + 1]
                for part in range(24):
                    t = part / 24
                    rx, ry = ax + (bx - ax) * t, ay + (by - ay) * t
                    if abs(ry - y) < step / 2 and 0 <= int(rx // step) < len(line):
                        line[int(rx // step)] = "#"
        lines.append("".join(line))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt", help="scene description; background detected from it")
    source.add_argument("--brief", type=Path, help="a brief JSON file")
    source.add_argument("--setting", help="background id, bypassing detection")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--region-m", type=int, default=512)
    parser.add_argument("--spacing-m", type=int, default=8)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--map-width", type=int, default=60)
    args = parser.parse_args(argv)
    try:
        if args.brief:
            payload = json.loads(args.brief.read_text(encoding="utf-8"))
            pack = load_setting_pack(payload["setting"])
            brief = brief_from_dict(payload, pack)
        else:
            brief = compile_brief(args.prompt, args.seed) if args.prompt else \
                compile_brief(f"{args.setting} scene", args.seed)
            if args.setting:
                pack = load_setting_pack(args.setting)
                brief = brief_from_dict({**brief.to_dict(), "setting": args.setting,
                                         "era": pack.eras[0]}, pack)
            else:
                pack = load_setting_pack(brief.setting)
        terrain = plan_terrain(pack.id, seed=args.seed, region_m=args.region_m, spacing_m=args.spacing_m)
        plan = plan_siting(brief, pack, terrain)
        report = validate_siting(plan, brief, pack, terrain)
    except SceneError as exc:
        print(json.dumps({"code": exc.code, "message": str(exc)}, ensure_ascii=False))
        return 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(plan.to_dict(), ensure_ascii=False), encoding="utf-8")
    print(render_blocks(plan, args.map_width))
    print()
    print(f"setting={plan.setting} seed={plan.seed} region={plan.region_m}m")
    for key, value in plan.stats.items():
        print(f"  {key}: {value}")
    print(f"  validation: {report['state']}")
    for check in report["checks"]:
        if check["state"] != "pass":
            print(f"    FAIL {check['rule']}: {check['message']}")
    return 0 if report["state"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
