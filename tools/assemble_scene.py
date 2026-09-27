"""Assemble a scene through the whole pipeline and write the WIR package (stage F)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from world_builder.planning import (SceneError, assemble_scene, compile_brief, load_designs,
                                    load_setting_pack, plan_siting, plan_terrain, render_png, render_svg,
                                    validate_scene)
from world_builder.adapters.minecraft.city import CityExportError, export_city
from world_builder.adapters.minecraft.scene import project_for_minecraft
from world_builder.planning.designer import design


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt")
    source.add_argument("--setting")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--region-m", type=int, default=512)
    parser.add_argument("--spacing-m", type=int, default=8)
    parser.add_argument("--output", type=Path, help="write the WIR package JSON here")
    parser.add_argument("--svg", type=Path, help="write a top-down SVG plan here")
    parser.add_argument("--png", type=Path, help="write a raster plan here, for the artifacts record")
    parser.add_argument("--export-minecraft", type=Path, dest="minecraft",
                        help="write 128 m Sponge schematics here (projected into the adapter's vocabulary)")
    parser.add_argument("--interiors", action="store_true",
                        help="materialise interiors; the adapter needs stair geometry for that")
    args = parser.parse_args(argv)
    try:
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
    designs = []
    skipped = set()
    for site in siting.sites:
        template = templates.get(site.type)
        if template is None:
            skipped.add(site.type)
            continue
        block = siting.block(site.block_id)
        entry_side = "south" if abs(block.centre[1] - site.y0) < abs(block.centre[1] - site.y1) else "north"
        designs.append(design(site, pack.entry(site.type), pack, template,
                                       entry_side=entry_side, seed=args.seed))
    designs = tuple(designs)
    package = assemble_scene(brief, pack, terrain, siting, designs)
    report = validate_scene(package, terrain, siting, designs)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(package, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.svg:
        render_svg(package, terrain, siting, designs, args.svg)
    if args.png:
        render_png(terrain, siting, designs, args.png)
    if args.minecraft:
        try:
            export = export_city(project_for_minecraft(package), args.minecraft,
                                 include_interiors=args.interiors)
        except (CityExportError, ValueError) as exc:
            print(json.dumps({"code": getattr(exc, "code", "target.error"), "message": str(exc)},
                             ensure_ascii=False))
            return 1
        print(f"  minecraft: {export['chunk_count']} chunk(s), {export['box_count']} box(es), "
              f"{export['non_air_blocks']} block(s) -> {args.minecraft}")
    print(f"setting={pack.id} seed={args.seed} world={package['manifest']['world_id']}")
    print(f"  records: {report['record_count']} {report['kinds']}")
    print(f"  designs: {len(designs)}; no template yet for: {sorted(skipped)}")
    print(f"  validation: {report['state']}")
    for check in report["checks"]:
        if check["state"] != "pass":
            print(f"    FAIL {check['rule']}: {check['message']}")
    if args.output:
        print(f"  package: {args.output}")
    if args.svg:
        print(f"  plan: {args.svg}")
    if args.png:
        print(f"  record: {args.png}")
    return 0 if report["state"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
