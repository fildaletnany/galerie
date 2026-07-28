import pygame as pg
from settings import *


class ObjectRenderer:
    def __init__(self, game, artworks: dict):
        self.game = game
        self.screen = game.screen
        self.wall_textures = self.load_wall_textures(artworks)

    def draw(self):
        self.draw_background()
        self.render_game_objects()

    def draw_background(self):
        pg.draw.rect(self.screen, CEILING_COLOR, (0, 0, WIDTH, HALF_HEIGHT))
        pg.draw.rect(self.screen, FLOOR_COLOR, (0, HALF_HEIGHT, WIDTH, HEIGHT))

    def render_game_objects(self):
        list_objects = sorted(self.game.raycasting.objects_to_render, key=lambda t: t[0], reverse=True)
        for depth, image, pos in list_objects:
            self.screen.blit(image, pos)

    @staticmethod
    def get_texture(path, res=(TEXTURE_SIZE, TEXTURE_SIZE)):
        texture = pg.image.load(path).convert_alpha()
        return pg.transform.scale(texture, res)

    def load_wall_textures(self, artworks: dict) -> dict:
        textures = {
            1: self.get_texture('resources/textures/1.png'),
            5: self.get_texture('resources/textures/5.png'),
        }
        textures.update(artworks)
        return textures

    def add_artworks(self, artworks: dict):
        self.wall_textures.update(artworks)

    def set_artworks(self, artworks: dict):
        for texture_id in list(self.wall_textures.keys()):
            if texture_id >= ARTWORK_FIRST_TEXTURE_ID:
                del self.wall_textures[texture_id]
        self.wall_textures.update(artworks)