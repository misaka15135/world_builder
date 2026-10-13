## Entry height relative to D's road

Before creating a floor, compute the walkable entry height in LOCAL site
coordinates: entry_cell.z = touching_road.bounds.max[2] - site.bounds.min[2].
For the common flat case, D site Z starts at 1 and road Z is [1,2]; therefore
the entry air cell is local Z=1, NOT Z=2. Give that cell solid support at
local Z [0,1], usually a single floor slab. Do not stack a 1 m foundation
AND another 1 m floor under the entry; that raises the door above the road.
If a foundation is not required by D, omit a separate foundation part.

The entry must be on the site perimeter edge that D's road actually touches.
If the road is immediately south of the site's min Y edge, entry_cell.y=0;
if north, y=site_depth-1; if west, x=0; if east, x=site_width-1.
All route cells begin at that entry cell and keep the same Z for a flat,
single-storey house. A clear room box should begin at that walk level, and
all route cells need two clear air blocks above a solid floor.
