"""Versioned compact single-room E proposal and validated cuboid projection."""
from __future__ import annotations

from .contracts import COMPACT_E_PAYLOAD, PAYLOADS, validate_schema
from .validation import cell_in, require


def _box(x0, y0, z0, x1, y1, z1):
    return {"min": [x0, y0, z0], "max": [x1, y1, z1]}


def _entry(side, width, depth):
    if side == "south":
        return [width // 2, 0, 1], [width // 2, 1, 1], [0, -1]
    if side == "north":
        return [width // 2, depth - 1, 1], [width // 2, depth - 2, 1], [0, 1]
    if side == "west":
        return [0, depth // 2, 1], [1, depth // 2, 1], [-1, 0]
    return [width - 1, depth // 2, 1], [width - 2, depth // 2, 1], [1, 0]


def available_entry_sides(plans, scope_id):
    site = next((site for site in plans["D"]["sites"] if site["id"] == scope_id), None)
    require(site is not None, "building.site", "Unknown E site")
    origin = site["bounds"]["min"]
    width, depth = [site["bounds"]["max"][i] - origin[i] for i in (0, 1)]
    sides = []
    for side in ("south", "north", "west", "east"):
        entry, _, delta = _entry(side, width, depth)
        outside = [origin[0] + entry[0] + delta[0], origin[1] + entry[1] + delta[1],
                   origin[2] + entry[2]]
        if any(cell_in([outside[0], outside[1], outside[2] - 1], road["bounds"])
               and not cell_in(outside, road["bounds"]) for road in plans["D"]["roads"]):
            sides.append(side)
    return sides


def project_compact_building(blueprint, plans, scope_id):
    validate_schema(blueprint, COMPACT_E_PAYLOAD, "building.blueprint_schema")
    require(blueprint["site_id"] == scope_id, "building.scope", "Blueprint site_id differs from E scope")
    site = next((site for site in plans["D"]["sites"] if site["id"] == scope_id), None)
    require(site is not None, "building.site", "Unknown E site")
    width, depth, height = [site["bounds"]["max"][i] - site["bounds"]["min"][i] for i in range(3)]
    require(width >= 5 and depth >= 5 and height >= 4, "building.capacity",
            "Compact room requires site width/depth >=5 m and height >=4 m; revise D")
    sides = available_entry_sides(plans, scope_id)
    require(blueprint["entry_side"] in sides, "building.entry_side",
            f"Entry must face a road touching D site; available sides: {', '.join(sides) or 'none'}")
    entry, access, _ = _entry(blueprint["entry_side"], width, depth)
    parts = []

    def part(id, role, bounds, material):
        if all(bounds["min"][i] < bounds["max"][i] for i in range(3)):
            parts.append({"id": id, "role": role, "bounds": bounds, "material": material})

    part("floor", "floor", _box(0, 0, 0, width, depth, 1), blueprint["floor_material"])
    wall = blueprint["wall_material"]
    top = height - 1
    centre_x, centre_y = width // 2, depth // 2
    if blueprint["entry_side"] == "south":
        part("wall_south_a", "wall", _box(0, 0, 1, centre_x, 1, top), wall)
        part("wall_south_b", "wall", _box(centre_x + 1, 0, 1, width, 1, top), wall)
    else:
        part("wall_south", "wall", _box(0, 0, 1, width, 1, top), wall)
    if blueprint["entry_side"] == "north":
        part("wall_north_a", "wall", _box(0, depth - 1, 1, centre_x, depth, top), wall)
        part("wall_north_b", "wall", _box(centre_x + 1, depth - 1, 1, width, depth, top), wall)
    else:
        part("wall_north", "wall", _box(0, depth - 1, 1, width, depth, top), wall)
    if blueprint["entry_side"] == "west":
        part("wall_west_a", "wall", _box(0, 1, 1, 1, centre_y, top), wall)
        part("wall_west_b", "wall", _box(0, centre_y + 1, 1, 1, depth - 1, top), wall)
    else:
        part("wall_west", "wall", _box(0, 1, 1, 1, depth - 1, top), wall)
    if blueprint["entry_side"] == "east":
        part("wall_east_a", "wall", _box(width - 1, 1, 1, width, centre_y, top), wall)
        part("wall_east_b", "wall", _box(width - 1, centre_y + 1, 1, width, depth - 1, top), wall)
    else:
        part("wall_east", "wall", _box(width - 1, 1, 1, width, depth - 1, top), wall)
    part("roof", "roof", _box(0, 0, top, width, depth, height), blueprint["roof_material"])
    result = {"site_id": scope_id, "concept": blueprint["concept"], "parts": parts,
              "spaces": [{"id": "main_room", "programme": blueprint["room_programme"],
                          "bounds": _box(1, 1, 1, width - 1, depth - 1, top),
                          "access_cell": access}],
              "entry_cell": entry, "routes": [{"space_id": "main_room", "cells": [entry, access]}]}
    validate_schema(result, PAYLOADS["E"], "building.projected_schema")
    return result
