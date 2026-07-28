import pygame as pg
from settings import ARTWORK_FIRST_TEXTURE_ID, ROOM_DOOR_TEXTURE_ID

ENDCAP_CLEARANCE = 4


def build_corridor(num_artworks: int) -> list[list]:
    """
    Generate a gallery corridor for num_artworks paintings.

    Layout (example, 6 north + 6 south):
      north wall:  [1, 1, 10,  1, 11, … 15,  1, 1]
      corridor x3: [1, 0,  0,              0, 0, 1]
      south wall:  [1, 1, 16,  1, 17, … 21,  1, 1]

    Artworks are separated by plain wall tiles so frames don't bleed together.
    IDs 10 … 10+north_count-1 on north; 10+north_count … 10+num_artworks-1 on south.
    """
    if num_artworks == 0:
        return [
            [1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 1],
            [ROOM_DOOR_TEXTURE_ID, 0, 0, 0, 0, 0, ROOM_DOOR_TEXTURE_ID],
            [1, 0, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 1, 1],
        ]

    slot_count = (num_artworks + 1) // 2
    north_slots = [None] * slot_count
    south_slots = [None] * slot_count

    # Stable placement: every new artwork only appends to the current tail slot.
    # Existing tiles keep their previous positions when the gallery expands.
    for i in range(num_artworks):
        texture_id = ARTWORK_FIRST_TEXTURE_ID + i
        slot = i // 2
        if i % 2 == 0:
            north_slots[slot] = texture_id
        else:
            south_slots[slot] = texture_id

    def make_wall(art_slots: list) -> list:
        # Pattern: [1, 1, id_or_1, 1, id_or_1, …, 1, 1]
        row = [1, 1]
        for i, art_id in enumerate(art_slots):
            row.append(art_id if art_id is not None else 1)
            if i < len(art_slots) - 1:
                row.append(1)
        # Keep a plain wall buffer before the terminal end so the hallway end
        # never shows rotating/changing artwork tiles while streaming.
        row.extend([1] * ENDCAP_CLEARANCE)
        row.extend([1, 1])
        return row

    north = make_wall(north_slots)
    south = make_wall(south_slots)

    width = len(north)
    corridor_upper = [1] + [0] * (width - 2) + [1]
    corridor_middle = [ROOM_DOOR_TEXTURE_ID] + [0] * (width - 2) + [ROOM_DOOR_TEXTURE_ID]
    corridor_lower = [1] + [0] * (width - 2) + [1]

    return [north, corridor_upper, corridor_middle, corridor_lower, south]


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
