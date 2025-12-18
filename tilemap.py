"""
Class for Tile map for 2D isometric RPG games.

Helpful urls while making:
https://clintbellanger.net/articles/isometric_math/
http://www-cs-students.stanford.edu/~amitp/gameprog.html#tiles
https://pikuma.com/blog/isometric-projection-in-games
https://web.archive.org/web/20190818212535/http://trac.bookofhook.com/bookofhook/trac.cgi/wiki/OverviewOfIsometricEngineDevelopment

TODO: . = undone, v = done but needs testing
. save selected tile location if mouse goes outside world bounds
v make a generalized way to select arbitrary tile
. make the center of the viewport
. make the player character tile
. center it on the viewport
"""

import pygame

pygame.init()

#region helper classes
# not just for vectors, but for generic 2-tuples because why not?
class Vec2d():
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.x_half = self.x / 2
        self.y_half = self.y / 2
        self.value = f"{self.x}, {self.y}" # for debugging

# for the tiles that make up the map. still need to figure out what properties go where.
class Tile:
    def __init__(self, img, x, y, traversable):
        self.image = img
        self.x = x
        self.y = y
        self.traversable = traversable # needed here? could do sth separate in generate_collsion_layer().
        self.world_coordinate = Vec2d(0, 0) # for identifying specific tiles, e.g. entrance/exit tiles.
#endregion

#region TileMap class
class TileMap:
    """ requirements for a tilemap class (* = done or mostly done):
    (functions depending on outside data inject those dependencies)
    * tile class
    * world grid with size and origin
    * level loading function
    * sprite atlas
    camera (fixed on player)
    * terrain layer
    object layer
    entity layer
    collision layer
    drawing of all layers done with double for loops
    drawing each layer bottom to top for each individual tile position 
    map boundaries
    entrances and exits
    * loading level data
    level data generation for dungeons
    * drawing function
    update function that updates each layer """
    def __init__(self, drawing_surf, viewport_size, fixed, level="levels\\lvl.txt"):
        self.drawing_surf = drawing_surf
        self.viewport_size = viewport_size
        self.map_data = level # data used to draw map loaded from external file.
        self.map_is_fixed = fixed # does the map need to be loaded from a file as opposed to generated?
        self.map_loaded = False # did we already create this map?
        self.terrain_sprites = {
            "default" : pygame.image.load("res\\isotile-outline.png").convert_alpha(),
            "empty"   : pygame.image.load("res\\isotile-empty.png").convert_alpha(),
            "filled"  : pygame.image.load("res\\isotile-filled.png").convert_alpha(),
            "corners" : pygame.image.load("res\\isotile-colored-corners.png").convert_alpha(),
        }
        """ map layers follow this order:
        terrain first because it's the first drawn, and could be traversable or not.
        object second because objects lay on the terrain.
        entity third because monsters can walk over items on the ground.
        collision fourth because we won't know whether something is traversable
        (e.g. if a monster walks to a tile, you can't walk through them). """
        self.map_terrain_layer   = [[]]
        self.map_object_layer    = [[]]
        self.map_entity_layer    = [[]]
        self.map_collision_layer = [[]]
        self.map_size   = Vec2d(3, 3)
        self.map_origin = Vec2d(4.5, 4.5) # 4.5, 4.5 is the cell at the center of the screen,
        # where "cell" means the rectangle surrounding a tile - a tile's drawing rect.
        # origin's location based on the top left corner of a cell.
        self.map_offset = Vec2d(0, 0) # used for moving the camera.
        self.map_player_position = Vec2d(0, 0)
        #self.map_entrance = None
        #self.map_exit = None
        self.tile_size = Vec2d(64, 32)
        #self.sprite_atlas = None
        #self.camera = None
        if self.map_loaded == False:
            self.generate_terrain_layer() # needed here?

    #region map drawing functions
    def to_isometric_grid(self, cell):
        """ used when defining the x y of the cells on the map grid as opposed to the screen.
        returns a position corresponding to a rectangle on the screen around a diamond-shaped tile.
        requires further processing to exactly correspond to each individual tile,
        bc rn it's an up/down grid of rectangles that don't exactly line up with the isometric map. """
        return Vec2d(
            int((self.map_origin.x * self.tile_size.x) + (cell.x - cell.y) * (self.tile_size.x_half)),
            int((self.map_origin.y * self.tile_size.y) + (cell.x + cell.y) * (self.tile_size.y_half)))

    def tile_center(self, position):
        """ returns the pixel coordinates of the center of the tile at position. 
        tile centers are weird in this codebase because the center of one tile
        is the corner of another tile. so if you're drawing or selecting tiles, which one 
        are you drawing? the tile at that position, or the tile whose corner is at that position?
        idk how to fix this yet. 
        maybe by making those two as separate data members inside the Tile class and
        then doing stuff using those? """
        tile = self.pixelxy_to_tilexy(position)
        return Vec2d(
            tile.x + self.tile_size.x_half,
            tile.y + self.tile_size.y_half)

    def pixelxy_to_world_coord(self, position):
        """ takes a set of screen coordinates and returns the world coordinate of the tile there.
        pixel coord -> world coord
        returns which section of the screen the position is in as a cell.
        needed because we're just drawing rectangles of diamond-shaped pictures
        as opposed to skewing the entire coordinate plane to draw rectangles that
        look like diamonds because of the skewing.
        cell defined as: (position.x // self.tile_size.x, position.y // self.tile_size.y) """

        # offset into cell
        offsetx = position.x % self.tile_size.x
        offsety = position.y % self.tile_size.y
        
        # specific cell
        selected = Vec2d(
            int(((position.y // self.tile_size.y) - self.map_origin.y) + ((position.x // self.tile_size.x) - self.map_origin.x)),
            int(((position.y // self.tile_size.y) - self.map_origin.y) - ((position.x // self.tile_size.x) - self.map_origin.x)))
        """ simplified (for reference):
            (cell.y - origin.y) + (cell.x - origin.x),
            (cell.y - origin.y) - (cell.x - origin.x) """
        
        # color of one of the four corners of the picture res\isotile-colored-corners.png,
        # used to shift our regard onto tiles around each cell,
        # instead of an up/down grid of rectangles that doesn't cover each tile drawn.
        # (am i using "tile" and "cell" inconsistently in this codebase? pls check)
        color_at_offset = self.terrain_sprites["corners"].get_at((int(offsetx), int(offsety)))
        color = color_at_offset[:3]
        if color == (255, 0, 0): selected.y += 1
        if color == (0, 255, 0): selected.y -= 1
        if color == (0, 0, 255): selected.x -= 1
        if color == (255, 255, 0): selected.x += 1
        
        return selected
    
    def world_coord_to_pixelxy(self, world_coord):
        """ converts world coord to on-screen pixel coord for drawing.
        used for when something happens around the player and we need to 
        know which tile relative to the player we're working with.
        world coord -> pixel coord """
        # find a tile at specific world coords
        tile = self.map_terrain_layer[world_coord.x][world_coord.y]
        
        # print(f"({tile.world_coordinate.x}, {tile.world_coordinate.y}) -> [{tile.x}, {tile.y}]")
        return Vec2d(tile.x, tile.y)

    def pixelxy_to_tilexy(self, position):
        """ converts on-screen coords to on-screen coords of a tile on the map
        after the map grid is converted to isometric coords.
        the "on-screen coords" are the top-left corner of the tile's rectangle.
        pixel coord -> pixel coord """
        offsetx = position.x % self.tile_size.x
        offsety = position.y % self.tile_size.y

        selected = Vec2d(
            ((position.y // self.tile_size.y) - self.map_origin.y) + ((position.x // self.tile_size.x) - self.map_origin.x),
            ((position.y // self.tile_size.y) - self.map_origin.y) - ((position.x // self.tile_size.x) - self.map_origin.x))

        color_at_offset = self.terrain_sprites["corners"].get_at((int(offsetx), int(offsety)))
        color = color_at_offset[:3]
        if color == (255, 0, 0): selected.y += 1
        if color == (0, 255, 0): selected.y -= 1
        if color == (0, 0, 255): selected.x -= 1
        if color == (255, 255, 0): selected.x += 1

        return self.to_isometric_grid(selected)

    def map_center_tile(self):
        """ for locating player's position.
        returns the position of the tile at the very center of the viewport.
        self.viewport_size accounts for there being a HUD,
        and draws at the center of the viewport minus one tile height and half width. 
        
        is this the best general behavior? what if I want a cinematic at some point?
        maybe have an optional parameter for offsetting from center? """
        # might need cell and selected in here too. that might be the issue.
        """
        since pixelxy_to_tilexy returns a cell, we need to subtract
        half the width/height to return the correct cell.
        we need to subtract instead of add because pixelxy_to_tilexy
        returns a cell that itself needs to be adjusted.
        
        need to make test cases for why the offsets need to be as they are:

        1. putting tile_cell as pixelxy_to_tilexy viewport_size half 
           while tile_center adds tile_size half 
        draws at world (2, 0), not (0, 0), one cell to the right and down,
        and returns (1, 0) for player location (red dot is on tile (1, 0))
        and (256, 160) for player screen position (tile xy of world (0, 1).
        
        2. putting tile_cell as pixelxy_to_tilexy viewport_size half 
           while tile_center returns straight-up cell xy 
        returns position (288, 144) which is location (0, 0), but draws at (1, 0)
        because (288, 144) is both the center of tile (0, 0) and the top left corner of (1, 0)."""
        # tile_cell = self.pixelxy_to_tilexy(self.viewport_size.x_half, self.viewport_size.y_half)
        """
        3. putting tile_cell as pixelxy_to_tilexy viewport_size half - tile_size half
           while tile_center returns straight xy 
        draws at (-1, 0) and returns (-1, 0) for player location! that means they line up.
        however, the tile position on the screen is up and to the left by one tile,
        thus no longer centered.

        4. putting tile_cell as pixelxy_to_tilexy viewport_size half - tile_size half 
           while tile_center adds tile_size half
        draws at (0, 3) (192, 192) and returns (-1, 0) for player location.
        (-1, 0) is the drawing focus for tile (0, 0), but also the center of tile (-1, 0).
        maybe this could be fixed by calculating the offset within the regarded tile? """
        tile_cell = self.pixelxy_to_tilexy(Vec2d(
            self.viewport_size.x_half - self.tile_size.x_half, 
            self.viewport_size.y_half - self.tile_size.y_half))
        # now we need to adjust to the center of that cell:
        tile_center = Vec2d(
            int(tile_cell.x + self.tile_size.x_half),
            int(tile_cell.y + self.tile_size.y_half))
        """
        what if i just return something different?
        5. returning tile_cell as pixelxy_to_tilexy viewport_size half - tile_size half
        draws at (224, 176) (0, 2), returns (-1, 0) for player location,
        and draws the player on tile (-1, 0) to the left of the viewport center.
        so the drawing is on tile (-1, 0) and the player location is (-1, 0).

        6. returning tile_cell as pixelxy_to_tilexy viewport_size half
        draws at (320, 160) (1, 0), returns (1, 0) for player location,
        and draws to the right of the viewport center. """
        return tile_center
    
    # takes a world coordinate and returns the tile at that location.
    def map_tile_at(self, world_coord):
        return self.map_terrain_layer[world_coord.x][world_coord.y]

    # returns the world coords of the player.
    # does the TileMap class know where the player is? bc player is defined in a separate class.
    def player_location(self, player): pass

    # moves the map based on input provided outside the library,
    # by adjusting the map's drawing offset converted to isometric.
    def map_move(self, direction):
        # cell and selected do the conversion.
        cell = Vec2d(
            self.map_origin.x // self.tile_size.x, 
            self.map_origin.y // self.tile_size.y)
        selected = Vec2d(
            (cell.y - self.map_origin.y) + (cell.x - self.map_origin.x),
            (cell.y - self.map_origin.y) - (cell.x - self.map_origin.x))

        """ increment adjusts based on tile size. each tile is half as tall as wide. 
        therefore, moving up/down needs to adjust y by half as much as x. """
        increment = Vec2d(self.tile_size.x_half / 2, self.tile_size.y_half / 4)

        """ movement doesn't work right. the angle it moves along is slightly off.
        also moving leftward is twice as fast as moving rightward for some reason. 
        directions opposite of actual expected player movement.
        will be adjusted when the problems are worked out. """
        if direction == "north": # toward top right corner of screen
            selected.x += increment.x
            selected.y -= increment.y
        if direction == "south": # toward bottom left
            selected.x -= increment.x
            selected.y += increment.y
        if direction == "west": # toward top left
            selected.x -= increment.x
            selected.y -= increment.y
        if direction == "east": # toward bottom right
            selected.x += increment.x
            selected.y += increment.y
        # following not used yet:
        if direction == "up": # top
            selected.y -= increment.y
        if direction == "down": # bottom
            selected.y += increment.y
        if direction == "left": # left side
            selected.x -= increment.x
        if direction == "right": # right side
            selected.x += increment.x

        self.map_offset.x += selected.x
        self.map_offset.y += selected.y

    # draws a specific tile at a specific position on the screen.
    # tile_image: Tile.image
    def draw_at(self, tile_image, position):
        self.drawing_surf.blit(tile_image, (position.x, position.y, self.tile_size.x, self.tile_size.y))

    # draws a specific tile at a specific world coordinate.
    def draw_at_loc(self, tile_image, location):
        loc = self.to_isometric_grid(location)
        tile = Tile(tile_image, loc.x, loc.y, True)
        tile.world_coordinate.x = location.x
        tile.world_coordinate.y = location.y
        self.map_terrain_layer[location.x][location.y] = tile
        self.drawing_surf.blit(tile.image, (
            tile.x + self.map_offset.x, tile.y + self.map_offset.y, 
            self.tile_size.x, self.tile_size.y))

    # draw the entire level.
    def draw(self):
        for y in range(self.map_size.y):
            for x in range(self.map_size.x):
                self.drawing_surf.blit(
                    self.terrain_sprites["default"], (
                        self.map_terrain_layer[x][y].x + self.map_offset.x, 
                        self.map_terrain_layer[x][y].y + self.map_offset.y, 
                        x * self.tile_size.x, y * self.tile_size.y))

    #endregion

    #region map generation functions
    def generate_terrain_layer(self):
        """ loads terrain layer from external file if map is fixed,
        otherwise does dynamic level generation (not yet implemented).
        opens a text file containing a matrix of characters,
        loops through each character with nested loop,
        creates a tile based on what character it finds at that x y position.
        ensures the file is formatted correctly by striping newlines
        and padding each line to the same length.
        converted to 2d list and transposed to get the correct orientation. """
        if self.map_is_fixed:
            with open(self.map_data, "r") as f:
                
                # remove newlines to get a neat matrix.
                data = [line.rstrip("\n") for line in f]

                # this ensures that carelessness when writing the file doesn't hurt.
                # i can just type whatever and it comes out as an NxN matrix.
                length = max(data, key=len)
                data = [line.ljust(len(length)) for line in data]

                tiles = []
                
                for y in range(len(data)):
                    for x in range(len(data[y])):
                        loc = Vec2d(x, y)
                        cell = self.to_isometric_grid(loc)
                        # draw different tiles here with multiple if statements
                        if data[y][x] == "0":
                            # affixes x and y values in the tiles of the game map
                            tiles.append(Tile(self.terrain_sprites["default"], cell.x, cell.y, True))
                        else: # default to empty tile
                            tiles.append(Tile(self.terrain_sprites["empty"], cell.x, cell.y, False))
                        
                        # make world coordinates for each tile in the map.
                        # https://softwareengineering.stackexchange.com/questions/212808/treating-a-1d-data-structure-as-2d-grid
                        tiles[x+len(data[y])*y].world_coordinate.x = x
                        tiles[x+len(data[y])*y].world_coordinate.y = y
                
                def list_to_2d(data, columns):
                    if len(data) % columns != 0:
                        print("Error: The total number of elements must be divisible by the number of columns.")
                        return None # raises NoneType error if not divisible
                    return [data[i : i + columns] for i in range(0, len(data), columns)]
                
                def transpose(matrix):
                    return [list(row) for row in zip(*matrix)]

                self.map_terrain_layer = transpose(list_to_2d(tiles, len(data[0])))
                self.map_size.x = len(data[0])
                self.map_size.y = len(data)
            
            self.map_loaded = True
        else: # do dynamic level generation here
            pass

    def generate_object_layer(self): pass
    def generate_entity_layer(self): pass
    def generate_collision_layer(self): pass
    
    def inside_world_bounds(self, position):
        cell = Vec2d(position.x // self.tile_size.x, position.y // self.tile_size.y)
        selected = Vec2d(
            (cell.y - self.map_origin.y) + (cell.x - self.map_origin.x),
            (cell.y - self.map_origin.y) - (cell.x - self.map_origin.x))
        
        return (selected.x >= 0 and selected.x < self.map_size.x and 
                selected.y >= 0 and selected.y < self.map_size.y)
    
    #endregion

    def print_world_coords(self): # debug
        for x in range(self.map_size.x):
            for y in range(self.map_size.y):
                tile = self.map_terrain_layer[x][y]
                print(f"Tile at [{x}, {y}] has world coords [{int(tile.world_coordinate.x)}, {int(tile.world_coordinate.y)}] and pixel position [{tile.x}, {tile.y}]")

    def update(self):
        """ for updating all map layers at once. """
        pass

#endregion

pygame.quit()