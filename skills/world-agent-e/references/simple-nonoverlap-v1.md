## Minimal non-overlapping building for this run

Prefer a small, auditable design: one supported floor, segmented perimeter
walls with a real door gap, one roof, one clear room and one short route from
the road-facing perimeter entry. Windows, planters, extra mats, aprons and
complex roof/gable layers are OPTIONAL; omit them if they risk collision.

Treat every part, including windows, decoration and landscape, as a SOLID
cuboid. Two parts must never share even a 1x1x1 m cell. A window is not an
overlay on a wall: split the wall into segments around the opening before
adding a window part, or omit the window. Do not lay a mat or apron cuboid on
top of a floor cuboid in the same occupied cells; omit the redundant piece.
Do not put roof and gable cuboids into the same cells. Face contact is allowed.

Before returning JSON, compare every pair of part bounds: overlap exists only
when min(a.max[i], b.max[i]) > max(a.min[i], b.min[i]) on ALL three axes. If
any pair overlaps, remove the optional piece or split a wall/floor safely,
then recheck route headroom and support. Keep local min Z >= 0 and local max
Z <= D.site.maxZ-D.site.minZ.
