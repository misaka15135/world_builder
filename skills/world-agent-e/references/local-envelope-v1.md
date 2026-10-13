## Local envelope arithmetic for this run

Before writing any component, find the D site matching scope_id. Compute each
local dimension as D.site.bounds.max[i] - D.site.bounds.min[i]. The allowed local
envelope is [0, 0, 0] to those three dimensions; every part and space has
min >= 0 and max <= the matching dimension. D's global minimum height is NOT
extra local height. Example: if D site Z bounds are [1, 5], local Z spans
[0, 4], so a wall or roof with local max Z=5 is invalid. Check every max value,
including walls, lintels and roof, against the computed local envelope before
returning JSON. A one-storey building can fit a 1 m floor at local Z [0,1],
2 m of clear room at [1,3], and a 1 m roof at [3,4]; do not add a fifth level.

Also check that no two solid parts occupy the same integer cell. Adjacent
parts may share a face, not volume. A clear space cannot include any solid
part. Route cells need two clear blocks above a supporting floor and must
begin at the perimeter next to D's road at matching elevation.
