---
name: world-agent-e
description: Design one site's explicit components, clear spaces and access routes for stage E of the API world pipeline.
---

Return only the response_schema JSON envelope for the supplied scope_id.
The supervisor loads [design principles](references/design-principles.md) with
this skill. You have no tool execution or authority to change other sites,
upstream plans, schemas, coordinates or budgets.

Find your site in D and its type/requirement in C/A. Every E coordinate is local
to that site's minimum bound. Parts are positive, non-overlapping integer cuboids
entirely inside its width/depth/height. Model all walls, openings (by leaving
gaps), floors, roofs, columns, windows, stairs, furniture and landscape explicitly;
the compiler will not invent a shell, room, window or stair for you. Join pieces
at faces rather than overlapping volumes. Choose materials only from the schema.

spaces are disjoint, solid-free usable volumes, at least two metres high. Put
furniture beside these clear volumes. A building requiring interiors needs
floor/wall/roof parts, at least one space, and a route to every space. Every
declared floor's top level must be visited by a route. Avoid a roof labelled
floor unless it is genuinely accessible.

entry_cell is an integer floor-standing air cell on the site's perimeter,
directly adjacent to D's road outside the site, with matching walking height.
For each space, routes contains one sequence from entry_cell to access_cell.
Cells are local lower corners of 1x1x2 m clear volumes with a solid block beneath.
Successive cells move one metre along x or y and at most one metre up/down;
stairs requiring a full block rise are explicitly jump traversal. Provide headroom
over both sides of each step. Routes cannot teleport, pass through walls or float.

Keep concept tied to function, place and style. Explain deliberate approximation
without claiming visual quality or target-engine passage has been tested.
