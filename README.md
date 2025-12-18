TileMap class for isometric ARPGs

This library provides a set of tools for drawing 2D isometric tile maps in the style of Diablo 1, Hades, or Tower of Kalemonvo. It takes a Civ 1 style approach in drawing in that it divides the screen up into rectangles, transforms their x y values into a diamond-shaped grid, and adjusts the position of the mod of the rectangles using color picking on an invisible tile so that the tiles line up.

There are three classes in the library:
- Vec2d for vectors and 2-tuples
- Tile for the individual tiles making up the map
- TileMap for handling map drawing, collision, item placement, etc.


