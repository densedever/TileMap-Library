"""
Test for my TileMap library.

Source for initial map idea: https://www.youtube.com/watch?v=wbabAxuYGFU

TODO: 
- function for picking the tile at center of viewport for player position is bugged,
even though the function it uses that picks tiles under arbitrary pixel coords works fine.
the function draws over the correct square, but the world coordinate for its location is
one off.
- something is weird with the map movement. its angle is off, so the movement doesn't exactly
align with the tiles.
"""

import pygame
from pygame.locals import *

import tilemap

#region setup and initialization
pygame.init()
pygame.font.init()

HUD_height    = 129 # number acquired from counting pixels in the actual game
screen_size   = tilemap.Vec2d(640, 480)
viewport_size = tilemap.Vec2d(640, 480-HUD_height)

screen = pygame.display.set_mode((screen_size.x, screen_size.y))
pygame.display.set_caption("Tilemap Test")

font = pygame.font.Font(None, 24)

black = (0, 0, 0)
white = (255, 255, 255)

timer = pygame.time.Clock()
FPS = 25

HUD = {}
HUD["x"] = 0
HUD["height"] = HUD_height
HUD["y"] = screen_size.y - HUD_height
HUD["width"] = screen_size.x

# arguments: drawing surface | viewport size | fixed or dynamic map | level file
# last argument is optional - defaults to "levels/lvl.txt" if fixed is False.
starting_area = tilemap.TileMap(screen, viewport_size, True, "levels\\lvl.txt")
#endregion

#region main loop and helper constants
clicking = False
LEFT_MB   = 1
# MID_MB = 2, RIGHT_MB = 3, SCROLL_DN = 4, SCROLL_UP = 5

running = True
while running:

    screen.fill(white)
    timer.tick(FPS)
    
    mouse = tilemap.Vec2d(pygame.mouse.get_pos()[0], pygame.mouse.get_pos()[1])

    starting_area.update()

    #region drawing and debugging

    # draw the level map.
    starting_area.draw()
    
    # debug: display a highlighted tile where the mouse is.
    world_coords_at_mouse = starting_area.pixelxy_to_world_coord(mouse) # world coord of tile
    tilexy_under_mouse = starting_area.pixelxy_to_tilexy(mouse) # pixel coord of tile
    starting_area.draw_at(starting_area.terrain_sprites["filled"], tilexy_under_mouse)
    
    # debug: display a highlighted tile where the viewport center is.
    # viewport is 10 tiles wide by 11 tiles tall, so the center is up 1 tile
    # from the center, or 10 tiles diagonal from each corner meeting in the middle.
    starting_area.draw_at(starting_area.terrain_sprites["filled"], starting_area.map_center_tile())
    
    # debug: (red dot) center of viewport
    pygame.draw.rect(screen, "red", (viewport_size.x_half, viewport_size.y_half, 10, 10))
    
    # debug: (green rect) tile xy (top-left corner) of drawing rect.
    # "tile xy" and "drawing focus" in this codebase refers to the top-left corner of the drawing rect.
    pygame.draw.rect(screen, "green", (
        starting_area.map_center_tile().x, 
        starting_area.map_center_tile().y, 
        starting_area.tile_size.x, starting_area.tile_size.y), 2)
    
    """ the following doesn't print correct value.
    player position is (-1, 0) when it should be (0, 0) at start.
    this is because the corner of a tile and the center of the previous tile are the same.
    how to fix? maybe subtract one pixel from the x and y of the pixelxy_to_tilexy function? """
    
    # debug: (blue rect) player drawing rect.
    """ is world_coord_to_pixelxy working correctly? yes
    world_coord_to_pixelxy returns the top-left corner of the tile at those world coords.
    but player_location is (-1, 0) instead of (0, 0) at start, bc location is based on top-left corner of tile.
    "location" in this codebase refers to a world coordinate. "position" refers to pixel x and y."""
    pygame.draw.rect(screen, "blue", (
        starting_area.map_center_tile().x, 
        starting_area.map_center_tile().y, 
        starting_area.tile_size.x, starting_area.tile_size.y), 2)

    # display some debugging info about the map coordinates
    mouse_cursor_text_surf = font.render(
        f"Mouse : {mouse.x}, {mouse.y}", True, black)
    cell_text_surf = font.render(
        f"Cell : {mouse.x // starting_area.tile_size.x}, {mouse.y // starting_area.tile_size.y}", True, black)
    selected_world_coords_text_surf = font.render(
        f"World : {int(world_coords_at_mouse.x)}, {int(world_coords_at_mouse.y)}", True, black)
    tilexy_under_mouse_surf = font.render(
        f"Selected : {tilexy_under_mouse.x}, {tilexy_under_mouse.y}", True, black)
    player_location_surf = font.render(
        f"Player Loc : {starting_area.pixelxy_to_world_coord(starting_area.map_center_tile()).x}, {starting_area.pixelxy_to_world_coord(starting_area.map_center_tile()).y}", True, black)

    screen.blit(mouse_cursor_text_surf, (12, 12))
    screen.blit(cell_text_surf, (12, 36))
    screen.blit(selected_world_coords_text_surf, (12, 60))
    screen.blit(tilexy_under_mouse_surf, (12, 84))
    screen.blit(player_location_surf, (12, 108))

    # draw HUD on top of everything else
    pygame.draw.rect(screen, "black", (HUD["x"], HUD["y"], HUD["width"], HUD["height"]), 1)
    
    #endregion

    #region input handling
    if clicking:
        # test map movement with the mouse.
        if mouse.x < viewport_size.x_half and mouse.y < viewport_size.y_half:
            starting_area.map_move("west")
        if mouse.x > viewport_size.x_half and mouse.y < viewport_size.y_half:
            starting_area.map_move("north")
        if mouse.x < viewport_size.x_half and mouse.y > viewport_size.y_half:
            starting_area.map_move("south")
        if mouse.x > viewport_size.x_half and mouse.y > viewport_size.y_half:
            starting_area.map_move("east")
    #endregion

    #region event handling
    for event in pygame.event.get():
        if event.type == QUIT: 
            running = False
        if event.type == MOUSEBUTTONDOWN: 
            if event.button == LEFT_MB: 
                clicking = True
        if event.type == MOUSEBUTTONUP: 
            if event.button == LEFT_MB: 
                clicking = False
    #endregion

    pygame.display.update()
#endregion

pygame.quit()
