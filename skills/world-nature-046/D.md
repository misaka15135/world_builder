# 046 separated organic settlements

Return exactly the response envelope required by response_schema, without prose.
Plan four unique districts, all required: west_low x160..220 y180..240;
west_high x140..220 y430..500; east_low x540..610 y210..280;
east_high x530..600 y460..520. Coordinates/metres are RH X east, Y north.
Each settlement contains 16 houses/shops. Choose radius 104..112 (schema allows
98..112), home_percent and yaw_jitter. Scatter is seeded rejection sampling,
not rows/rings. It reserves a central square, avoids water/adjacent buildings,
orients facades approximately toward its hub with angular variety, and grades
house pads. Footprint-avoiding terrain A* roads connect the houses and settlements.
The castle sits on the north-east hill: x580..650 y650..680, yaw -22..22 degrees.
Two actual bridges at y288/548 connect both banks; roads are terrain material
regions, not floating strips. E recipes reuse the recorded accepted 045 models;
do not design new buildings. Title under 120 and concept under 600 characters.
