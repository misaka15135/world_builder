"""Plan the terrain for a scene and report whether it matches the background."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from world_builder.planning import (SceneError, compile_brief, load_terrain_spec, plan_terrain, render_preview,
                                    validate_terrain)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt", help="scene description; the background is detected from it")
    source.add_argument("--setting", help="background id, bypassing detection")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--region-m", type=int, default=512)
    parser.add_argument("--spacing-m", type=int, default=8, help="grid step in metres (4 = the export spacing)")
    parser.add_argument("--output", type=Path, help="write the plan JSON here")
    parser.add_argument("--preview-width", type=int, default=72)
    args = parser.parse_args(argv)
    try:
        setting = args.setting or compile_brief(args.prompt, args.seed).setting
        spec = load_terrain_spec(setting)
        plan = plan_terrain(setting, seed=args.seed, region_m=args.region_m, spacing_m=args.spacing_m)
        report = validate_terrain(plan, spec)
    except SceneError as exc:
        print(json.dumps({"code": exc.code, "message": str(exc)}, ensure_ascii=False))
        return 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(plan.to_dict(), ensure_ascii=False), encoding="utf-8")
    print(render_preview(plan, args.preview_width))
    print()
    print(f"setting={plan.setting} seed={plan.seed} region={plan.region_m}m spacing={plan.spacing_m}m "
          f"grid={plan.columns}x{plan.rows}")
    for key in ("min_m", "max_m", "mean_m", "min_slope_deg", "mean_slope_deg", "max_slope_deg",
                "water_fraction", "channel_count", "channel_length_m", "reserved_fraction"):
        if key in plan.stats:
            print(f"  {key}: {plan.stats[key]}")
    for channel in plan.channels:
        print(f"  {channel.id} ({channel.kind}): {len(channel.points)} points, {round(channel.length_m, 1)} m, "
              f"width {channel.width_m} m")
    print(f"  validation: {report['state']}")
    for check in report["checks"]:
        if check["state"] != "pass":
            print(f"    FAIL {check['rule']}: {check['message']}")
    return 0 if report["state"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
