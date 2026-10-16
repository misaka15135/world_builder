# 045 bounded city layout

Return the exact schema envelope. Include ALL 48 unique slot values from schema,
each once, and use all eight catalogue recipes at least once. At least 16 slots
must use home recipes and at least 16 shop recipes. Choose width 16..24 m,
depth 14..20 m, x_shift -4..4 m PER INSTANCE, so design choices affect actual WIR.
Slots row0..3 correspond to B's street_y. Columns 0..5 anchor x at
24/100/176/280/356/432. Side south means below the road with entry north;
side north means above the road with entry south. The local projector places
the footprint flush to the correct road edge; do not provide arbitrary geometry.
Choose castle_x=336 or 352; local castle footprint is [x,432,x+128,496].
Local policy adds roads, four river bridges, bank walks, city walls with aligned
openings, squares linked to streets and safe vegetation. You control a constrained
layout, not every coordinate; do not claim arbitrary urban design or old full-map
copying. Mix functions and footprints across districts rather than one recipe only.
