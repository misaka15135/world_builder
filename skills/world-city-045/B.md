# 045 bounded city base

Return only the exact response envelope and payload required by response_schema.
This is a fixed 512 m magic-medieval city, with 48 serviced building parcels,
four squares, a north-east castle and river crossings. Do not generate geometry.
Choose river_x from 248/256/264, width from 12/16/20. Ground is explicitly a flat
1 m platform; river bed .35 m, water .85 m, road/bridge tops 1.1 m. Four east-west
streets must be in row order: 80 +/-6, 176 +/-6, 272 +/-6, 368 +/-6 metres.
street_width 6..10. Two local north-south avenues at x=72 and x=328, bank walks,
gates and actual bridge decks are deterministic policy derived from these values.
No slopes, physics water simulation, curved rivers or independent A task exists.
