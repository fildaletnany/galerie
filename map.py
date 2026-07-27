import pygame as pg
import math
from settings import ARTWORK_FIRST_TEXTURE_ID


def build_corridor(num_artworks: int) -> list[list]:
    """
    Generate a gallery corridor for num_artworks paintings.

    Layout (example, 6 north + 6 south):
      north wall:  [1, 1, 10,  1, 11, … 15,  1, 1]
      corridor x2: [1, 0,  0,              0, 0, 1]
      south wall:  [1, 1, 16,  1, 17, … 21,  1, 1]

    Artworks are separated by plain wall tiles so frames don't bleed together.
    IDs 10 … 10+north_count-1 on north; 10+north_count … 10+num_artworks-1 on south.
    """
    if num_artworks == 0:
        return [
            [1, 1, 1, 1, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 1, 1, 1, 1],
        ]

    north_count = math.ceil(num_artworks / 2)
    south_count = num_artworks - north_count

    north_ids = list(range(ARTWORK_FIRST_TEXTURE_ID, ARTWORK_FIRST_TEXTURE_ID + north_count))
    south_ids = list(
        range(
            ARTWORK_FIRST_TEXTURE_ID + north_count,
            ARTWORK_FIRST_TEXTURE_ID + num_artworks
        )
    )

    def make_wall(art_ids: list, total_slots: int) -> list:
        # Pattern: [1, 1, id_or_1, 1, id_or_1, …, 1, 1]
        row = [1, 1]
        for i in range(total_slots):
            row.append(art_ids[i] if i < len(art_ids) else 1)
            if i < total_slots - 1:
                row.append(1)
        row.extend([1, 1])
        return row

    north = make_wall(north_ids, north_count)
    south = make_wall(south_ids, north_count)  # same width as north

    width = len(north)
    corridor = [1] + [0] * (width - 2) + [1]

    return [north, corridor[:], corridor[:], south]


class Map:
    def __init__(self, game, num_artworks: int):
        self.game = game
        self.mini_map = build_corridor(num_artworks)
        self.world_map = {}
        self.rows = len(self.mini_map)
        self.cols = len(self.mini_map[0])
        self.get_map()

    def set_artwork_count(self, num_artworks: int):
        self.mini_map = build_corridor(num_artworks)
        self.world_map = {}
        self.rows = len(self.mini_map)
        self.cols = len(self.mini_map[0])
        self.get_map()

    def get_map(self):
        for j, row in enumerate(self.mini_map):
            for i, value in enumerate(row):
                if value:
                    self.world_map[(i, j)] = value

    def draw(self):
        [pg.draw.rect(self.game.screen, 'darkgray', (pos[0] * 100, pos[1] * 100, 100, 100), 2)
         for pos in self.world_map]
