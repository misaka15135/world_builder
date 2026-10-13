## Clear-space box for this run

The declared space box is wholly EMPTY air, not the room's outer wall-to-wall
footprint. Keep it strictly inside walls and columns; exclude benches and
furniture from it. For a 10x8x4 local envelope with floor Z [0,1], outer
walls at X [0,1] and [9,10], and roof Z [3,4], a clear room may use
min [1,1,1], max [9,7,3] ONLY if no columns or furniture occupy those cells.
If posts/benches are inside that box, move them outside or shrink the box.
