# 045 recipe and castle design

Return only exact response_schema JSON. scope_id is one recipe ID or castle;
site_id must equal it. Design only that scope. Local execution instantiates the
recipe in every D-assigned footprint, substituting the instance ID explicitly.

Ordinary recipes: one or two floors for home, exactly two for shop; TWO room
uses per floor, and room_uses length exactly storeys. Heights 3.4..4 m and roof
height 1..2.5 m. Coordinate all eight intents: include BOTH stone and plaster
walls and at least TWO roof forms in the set. Suggested distinct roofs:
home_a gable/wood, home_b spire/slate, home_c gable/slate, home_d flat/wood,
shop_a gable/wood, shop_b spire/slate, shop_c flat/slate, shop_d gable/slate.
These are achievable suggestions, not an unregistered repair/fallback. Windows,
plinths, porch columns, floors, two rooms per level, furniture and stairs are
actually built by the established detailed constructor. No arbitrary boxes.

Castle scope uses its own schema, not ordinary building fields. Choose tower
height/roof, wall height, gate width and keep width/depth/roof/material. Four
hollow square towers with stepped roof silhouettes have no internal stairs or
walkable tower platforms; do NOT claim tower interiors are usable. The keep
is a two-floor detailed stone building. Courtyard/gate/approach are deterministic.
