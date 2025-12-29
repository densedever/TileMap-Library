"""
Class for drawing Tile maps for 2D isometric RPG games.

Helpful urls while making:
https://clintbellanger.net/articles/isometric_math/
http://www-cs-students.stanford.edu/~amitp/gameprog.html#tiles
https://pikuma.com/blog/isometric-projection-in-games
https://web.archive.org/web/20190818212535/http://trac.bookofhook.com/bookofhook/trac.cgi/wiki/OverviewOfIsometricEngineDevelopment

TODO: . = undone, v = done but needs testing
. save selected tile location if mouse goes outside world bounds
v make a generalized way to select arbitrary tile
v make the center of the viewport
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
        #self.map_entrance = None
        #self.map_exit = None
        self.tile_size = Vec2d(64, 32)
        #self.sprite_atlas = None
        #self.camera = None
        self.moving = False
        self.animation_frames_remaining = 0 # frames left in current movement animation.
        self.animation_target_offset = Vec2d(0, 0) # total offset to move during this animation.
        self.animation_increment = Vec2d(0, 0) # offset per frame.
        if self.map_loaded == False:
            self.generate_terrain_layer() # needed here?
        
        # initialize player location after terrain is generated.
        # use viewport center directly, not map_center_tile() which returns a drawing position
        center_position = Vec2d(
            int(self.viewport_size.x_half),
            int(self.viewport_size.y_half))
        self.map_player_location = self.pixelxy_to_world_coord(center_position)

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
        are you drawing? the tile underneath that position, or the tile whose corner is at 
        that position? idk how to fix this yet. """
        tile = self.pixelxy_to_tilexy(position)
        return Vec2d(
            tile.x + self.tile_size.x_half,
            tile.y + self.tile_size.y_half)

    def pixelxy_to_world_coord(self, position):
        """ takes a set of screen coordinates and returns the world coordinate of the tile there.
        pixel coord -> world coord
        determine which diamond tile contains the pixel:
        1. determine which rectangular cell the pixel is in.
        2. get the offset within that cell.
        3. use linear equations to test which 4 diamonds the pixel belongs to.
        
        ex: for a 64x32 isometric tile, the diamond edges have slopes:
        - top-right and bottom-left edges: slope = -0.5 (y decreases by 16 per 32x)
        - top-left and bottom-right edges: slope = 0.5 (y increases by 16 per 32x) """

        # adjust position to account for map offset (camera movement).
        adjusted_x = position.x - self.map_offset.x
        adjusted_y = position.y - self.map_offset.y

        # offset into cell (0 to tile_size-1).
        offsetx = adjusted_x % self.tile_size.x
        offsety = adjusted_y % self.tile_size.y
        offsetx_half = 0.5 * offsetx # because it's a repeated calculation.

        # base cell calculation.
        selected = Vec2d(
            int(((adjusted_y // self.tile_size.y) - self.map_origin.y) + ((adjusted_x // self.tile_size.x) - self.map_origin.x)),
            int(((adjusted_y // self.tile_size.y) - self.map_origin.y) - ((adjusted_x // self.tile_size.x) - self.map_origin.x)))
        
        # mathematical tile selection:
        # check if the pixel is inside the diamond or in one of the 4 corner regions.
        # diamond corners in cell coords: 
        # top (32,0), right (64,16), bottom (32,32), left (0,16)
        
        half_w = self.tile_size.x_half  # 32
        half_h = self.tile_size.y_half  # 16
        
        # diamond edge equations in cell coordinates (offsetx, offsety):
        # a point is inside the diamond if it satisfies all four inequalities:
        # - above top-left edge:     offsety > half_h - offsetx_half
        # - above top-right edge:    offsety > offsetx_half - half_h
        # - below bottom-right edge: offsety < 3 * half_h - offsetx_half
        # - below bottom-left edge:  offsety < offsetx_half + half_h
        
        # check each edge to see if we're in a corner region:
        
        # top-left corner (above the top-left edge).
        if offsety < half_h - offsetx_half:
            selected.x -= 1  # belongs to west tile.
        # top-right (above the top-right edge).
        elif offsety < offsetx_half - half_h:
            selected.y -= 1  # belongs to north tile.
        # bottom-right (below the bottom-right edge).
        elif offsety > 3 * half_h - offsetx_half:
            selected.x += 1  # belongs to east tile.
        # bottom-left (below the bottom-left edge).
        elif offsety > offsetx_half + half_h:
            selected.y += 1  # belongs to south tile.
        # else: inside the diamond, no adjustment needed.
        
        return selected
    
    def world_coord_to_pixelxy(self, world_coord):
        """ converts world coord to on-screen pixel coord for drawing.
        used for when something happens around the player and we need to 
        know which tile relative to the player we're working with.
        world coord -> pixel coord """
        tile = self.map_terrain_layer[world_coord.x][world_coord.y]
        return Vec2d(tile.x, tile.y)

    def pixelxy_to_tilexy(self, position):
        """ converts on-screen coords to on-screen coords of a tile on the map
        after the map grid is converted to isometric coords.
        the "on-screen coords" are the top-left corner of the tile's rectangle.
        pixel coord -> pixel coord 
        uses the same mathematical approach as pixelxy_to_world_coord. """
        
        offsetx = position.x % self.tile_size.x
        offsety = position.y % self.tile_size.y

        offsetx_half = 0.5 * offsetx

        selected = Vec2d(
            ((position.y // self.tile_size.y) - self.map_origin.y) + ((position.x // self.tile_size.x) - self.map_origin.x),
            ((position.y // self.tile_size.y) - self.map_origin.y) - ((position.x // self.tile_size.x) - self.map_origin.x))

        # same tile selection as pixelxy_to_world_coord
        half_w = self.tile_size.x_half
        half_h = self.tile_size.y_half
        
        # check if pixel is in a corner region outside the diamond
        if offsety < half_h - offsetx_half:
            selected.x -= 1
        elif offsety < offsetx_half - half_h:
            selected.y -= 1
        elif offsety > 3 * half_h - offsetx_half:
            selected.x += 1
        elif offsety > offsetx_half + half_h:
            selected.y += 1

        return self.to_isometric_grid(selected)

    def map_center_tile(self):
        """ for locating player's position.
        returns the position of the tile at the very center of the viewport.
        self.viewport_size accounts for there being a HUD,
        and draws at the center of the viewport minus one tile height and half width. 
        
        since pixelxy_to_tilexy returns a cell, we need to subtract 
        half the width/height to return the correct cell.
        we need to subtract instead of add because pixelxy_to_tilexy 
        returns a cell that itself needs to be adjusted. """
        tile_cell = self.pixelxy_to_tilexy(Vec2d(
            self.viewport_size.x_half - self.tile_size.x_half, 
            self.viewport_size.y_half - self.tile_size.y_half))
        
        tile_center = Vec2d(
            int(tile_cell.x + self.tile_size.x_half),
            int(tile_cell.y + self.tile_size.y_half))
        return tile_center
    
    def map_tile_at(self, world_coord):
        """ takes a world coordinate and returns the tile at that location. """
        return self.map_terrain_layer[world_coord.x][world_coord.y]

    def map_move(self, direction):
        """ initiates an animated movement between tiles happening over 4 frames, 
        with 1/4 tile movement per frame. movement only starts if not already animating. """
        
        # ignore input if already animating.
        if self.moving:
            return
        
        # direct pixel's movement to one full tile in isometric space.
        half_tile_w = self.tile_size.x_half  # 32
        half_tile_h = self.tile_size.y_half  # 16
        
        # where the animation is going to end up.
        target = Vec2d(0, 0)
        
        if direction == "north":  # toward top right
            target.x = -half_tile_w
            target.y = half_tile_h
        elif direction == "south":  # toward bottom left
            target.x = half_tile_w
            target.y = -half_tile_h
        elif direction == "west":  # toward top left
            target.x = half_tile_w
            target.y = half_tile_h
        elif direction == "east":  # toward bottom right
            target.x = -half_tile_w
            target.y = -half_tile_h
        elif direction == "up":  # pure vertical up on screen (combines north + west)
            target.x = 0
            target.y = -half_tile_h * 2
        elif direction == "down":  # pure vertical down on screen (combines south + east)
            target.x = 0
            target.y = half_tile_h * 2
        elif direction == "left":  # pure horizontal left on screen (combines west + south)
            target.x = -half_tile_w * 2
            target.y = 0
        elif direction == "right":  # pure horizontal right on screen (combines east + north)
            target.x = half_tile_w * 2
            target.y = 0
        
        # set up animation parameters.
        self.moving = True
        self.animation_frames_remaining = 4
        self.animation_target_offset = target
        self.animation_increment = Vec2d(target.x / 4, target.y / 4)

    def draw_at_position(self, tile_image, position):
        """ draws a specific tile at a specific position on the screen. """
        self.drawing_surf.blit(tile_image, 
            (position.x, position.y, self.tile_size.x, self.tile_size.y))

    def draw_at_location(self, tile_image, location):
        """ draws a specific tile at a specific world coordinate.
        that new tile that's spawned needs its world_coordinate set explicitly. """
        loc = self.to_isometric_grid(location)
        tile = Tile(tile_image, loc.x, loc.y, True)
        tile.world_coordinate.x = location.x
        tile.world_coordinate.y = location.y
        self.map_terrain_layer[location.x][location.y] = tile
        self.drawing_surf.blit(tile.image, (
            tile.x + self.map_offset.x, 
            tile.y + self.map_offset.y, 
            self.tile_size.x, self.tile_size.y))

    def draw(self, offset = Vec2d(0, 0)):
        """ draws the entire level based on player position.
        offset parameter adjusts to where that is. """
        if offset.x != 0 and offset.y != 0:
            self.map_offset.x = offset.x
            self.map_offset.y = offset.y
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
                        # draw different tiles here with multiple if statements.
                        if data[y][x] == "0":
                            # affixes x and y values in the tiles of the game map.
                            tiles.append(Tile(self.terrain_sprites["default"], cell.x, cell.y, True))
                        else: # default to empty tile.
                            if data[y][x] == "P": # mark player starting location.
                                self.map_player_location = Vec2d(x, y)
                            tiles.append(Tile(self.terrain_sprites["empty"], cell.x, cell.y, False))
                        
                        # make world coordinates for each tile in the map.
                        # https://softwareengineering.stackexchange.com/questions/212808/treating-a-1d-data-structure-as-2d-grid
                        tiles[x+len(data[y])*y].world_coordinate.x = x
                        tiles[x+len(data[y])*y].world_coordinate.y = y
                
                def list_to_2d(data, columns):
                    if len(data) % columns != 0:
                        print("Error: The total number of elements must be divisible by the number of columns.")
                        return None # raises NoneType error if not divisible.
                    return [data[i : i + columns] for i in range(0, len(data), columns)]
                
                def transpose(matrix):
                    return [list(row) for row in zip(*matrix)]

                tiles = list_to_2d(tiles, len(data[0]))
                self.map_terrain_layer = transpose(tiles)
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
        """ for updating all map layers at once. 
        handles animation of map movement over multiple frames. """
        if self.moving and self.animation_frames_remaining > 0:
            # apply the increment for this frame.
            self.map_offset.x += self.animation_increment.x
            self.map_offset.y += self.animation_increment.y
            
            self.animation_frames_remaining -= 1
            
            # stop animation when complete and update player location.
            if self.animation_frames_remaining == 0:
                self.moving = False
                # Update player's world coordinate based on center of viewport
                center_position = Vec2d(
                    int(self.viewport_size.x_half),
                    int(self.viewport_size.y_half))
                self.map_player_location = self.pixelxy_to_world_coord(center_position)

#endregion

pygame.quit()
