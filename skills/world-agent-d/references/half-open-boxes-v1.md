## Half-open box arithmetic for this run

All D bounds use integer metre half-open intervals: size[i] = max[i] - min[i].
Every site is a BUILDING ENVELOPE, not just its ground slab. For each site,
horizontal size must be at least 4 by 4 m and no larger than its C type.size_m;
its Z size must be at least 3 m and no larger than C type.max_height_m. If B's
flat ground height is 4 and the desired building height is 5 m, use site Z
[4, 9], NEVER [4, 5]. A complete valid example for C size_m [12, 9] and
max_height_m 5 is site bounds min [10, 10, 4], max [20, 18, 9]. Its local E
envelope will be [0, 0, 0] to [10, 8, 5].

A road is a separate, terrain-supported ONE-METRE-THICK cuboid. At terrain
height 4, use road Z [4, 5], NEVER [4, 4]. Keep it outside site envelopes,
touching a site along a full horizontal edge with the road top at site.min Z+1.
For the example site above, road bounds min [10, 8, 4], max [20, 10, 5]
touch the site's south edge without overlap. Road width must be at least 2 m.
Keep all districts disjoint, and put each site completely inside its district.
Check all min<max coordinates and type envelopes before emitting JSON.
