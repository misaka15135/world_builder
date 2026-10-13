# 042 magic street layout parameters, contract 0.1.1-style042

Return exactly the JSON specified by response_schema, echoing its version, request_id, stage and scope_id. Be concise. This is a bounded 64x64 metre magic-medieval street, not a full city. Required: exactly TWO residence sites, TWO shop sites, ONE plaza. No castle, water, walls or additional sites. You decide IDs, positions, dimensions, road position and concept.

The road runs east-west from x=2 to x=62; choose its south edge road_y (20..34) and road_width (4..8). Site x is its west edge; width is east-west 12..20m; depth is north-south 10..18m. bank=north places the building above the road with a south-facing door. bank=south places it below the road with a north-facing door. The local executor computes exact y coordinates and door orientation. Every site must fit within x,y=2..62: x+width<=62, north site's road_y+road_width+depth<=62, south site's road_y-depth>=2.

Sites on the SAME bank must have >=2 metres between their x intervals. One feasible pattern (you may change it within the rules): north x=4,width=14; x=20,width=16; x=38,width=14. South x=8,width=16 and x=30,width=18. This is dimensional guidance, not a required layout. Prefer buildings on both sides and a visible plaza. Do not output rectangles, doorway sides or terrain fields: only the parameter fields in response_schema.
