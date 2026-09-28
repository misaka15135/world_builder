"""Design every sited building for a scene (stage E)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from world_builder.planning import (BuildingDesign, SceneError, compile_brief, load_designs,
                                    load_setting_pack, plan_siting, plan_terrain, validate_design)
from world_builder.planning.designer import (CompoundDesign, CylinderDesign, OpenSpaceDesign,
                                             design as design_for, validate_compound, validate_cylinder,
                                             validate_open_space)


def render_plan(design, width: int = 56) -> str:
    """A per-storey plan: walls, rooms, the partition slot, the stair void, the door."""
    storey = design.storeys[0]
    span_x, span_y = design.x1 - design.x0, design.y1 - design.y0
    step = max(span_x / width, span_y / (width / 2.2))
    rows = int(span_y / step)
    lines = []
    for row in range(rows):
        y = design.y0 + (row + 0.5) * step
        line = []
        for column in range(int(span_x / step)):
            x = design.x0 + (column + 0.5) * step
            glyph = "#"
            if storey.x0 <= x <= storey.x1 and storey.y0 <= y <= storey.y1:
                glyph = "."
            for room in storey.rooms:
                if room.x0 <= x <= room.x1 and room.y0 <= y <= room.y1:
                    glyph = room.use[0].upper()
            if storey.partition_x_m is not None and abs(x - storey.partition_x_m) < step and \
                    storey.y0 <= y <= storey.y1:
                glyph = "|"
            if design.stair and design.stair["void"][0] <= x <= design.stair["void"][1] and \
                    design.stair["void"][2] <= y <= design.stair["void"][3]:
                glyph = "S"
            line.append(glyph)
        lines.append("".join(line))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt")
    source.add_argument("--setting")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--region-m", type=int, default=512)
    parser.add_argument("--spacing-m", type=int, default=8)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--show", help="print the ground-floor plan of one building type")
    args = parser.parse_args(argv)
    try:
        # `--setting` means the setting's own registered prompt, exactly as
        # `assemble_scene.py` reads it: synthesising a "<setting> scene" prompt
        # here made the two tools disagree about the same setting (harbour had
        # 13 designs this way and 14 through the scene tool, measured
        # 2026-09-28), which is what work order 016's input-parity check is for.
        pack = load_setting_pack(args.setting) if args.setting else None
        brief = compile_brief(args.prompt if args.prompt else pack.default_prompt, args.seed)
        pack = pack or load_setting_pack(brief.setting)
        if brief.setting != pack.id:
            raise SceneError("brief.setting", f"default prompt for {pack.id!r} resolved to {brief.setting!r}")
        terrain = plan_terrain(pack.id, seed=args.seed, region_m=args.region_m, spacing_m=args.spacing_m)
        siting = plan_siting(brief, pack, terrain)
        templates = load_designs(pack.id)
    except SceneError as exc:
        print(json.dumps({"code": exc.code, "message": str(exc)}, ensure_ascii=False))
        return 1
    designs, skipped, failures = [], [], []
    for site in siting.sites:
        template = templates.get(site.type)
        if template is None:
            skipped.append(site.type)
            continue
        block = siting.block(site.block_id)
        entry_side = "south" if abs(block.centre[1] - site.y0) < abs(block.centre[1] - site.y1) else "north"
        try:
            design = design_for(site, pack.entry(site.type), pack, template, entry_side=entry_side,
                                seed=args.seed)
        except SceneError as exc:
            # Scoped failure (work order 018): one plot that cannot be designed is
            # recorded against that plot and the rest of the city still runs.
            failures.append({"design": site.id, "type": site.type, "code": exc.code,
                             "checks": [{"rule": exc.code, "state": "fail", "message": str(exc)}]})
            continue
        # Every design kind has its own validator (work orders 017/018): a tank
        # farm and a castle are not buildings, so they must not be handed to the
        # building rule.
        if isinstance(design, OpenSpaceDesign):
            report = validate_open_space(design, site)
        elif isinstance(design, CompoundDesign):
            report = validate_compound(design, site)
        elif isinstance(design, CylinderDesign):
            report = validate_cylinder(design, site)
        else:
            report = validate_design(design, site, pack.entry(site.type))
        if report["state"] != "pass":
            failures.append({"design": design.id, "type": design.type,
                             "checks": [check for check in report["checks"] if check["state"] != "pass"]})
        designs.append((design, report))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"setting": pack.id, "brief": brief.to_dict(),
                                           "designs": [design.to_dict() for design, _ in designs]},
                                          ensure_ascii=False), encoding="utf-8")
    if args.show:
        match = next((design for design, _ in designs if design.type == args.show), None)
        if match is None:
            print(json.dumps({"code": "design.not_found", "message": f"no {args.show} was sited"},
                             ensure_ascii=False))
            return 1
        print(json.dumps(match.to_dict(), ensure_ascii=False, indent=1) if isinstance(match, OpenSpaceDesign)
              else render_plan(match))
        print()
    by_type: dict[str, int] = {}
    for design, _ in designs:
        by_type[design.type] = by_type.get(design.type, 0) + 1
    # Only buildings have storeys, stairs and furniture (work orders 017/018).
    storeys = [len(design.storeys) for design, _ in designs if isinstance(design, BuildingDesign)]
    print(f"setting={pack.id} seed={args.seed} designs={len(designs)} skipped={len(skipped)} "
          f"failures={len(failures)}")
    print(f"  by type: {dict(sorted(by_type.items()))}")
    if storeys:
        print(f"  storeys: min {min(storeys)} max {max(storeys)} mean {round(sum(storeys)/len(storeys), 2)}")
        print(f"  heights: max {max(round(design.height_m, 1) for design, _ in designs)} m")
        with_stair = sum(1 for design, _ in designs if isinstance(design, BuildingDesign) and design.stair)
        print(f"  with stair: {with_stair}; furniture pieces: "
              f"{sum(len(design.furniture) for design, _ in designs if isinstance(design, BuildingDesign))}; "
              f"open spaces: {sum(1 for design, _ in designs if isinstance(design, OpenSpaceDesign))}")
    if skipped:
        print(f"  no design template yet for: {sorted(set(skipped))}")
    for failure in failures[:5]:
        print(f"  FAIL {failure['type']}: {[check['rule'] for check in failure['checks']]}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
