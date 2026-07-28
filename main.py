import pygame as pg
import sys
import math
from settings import *
from map import *
from player import *
from raycasting import *
from object_renderer import *
from sprite_object import *
from object_handler import *
from weapon import *
from sound import *
from artwork_loader import ArtworkStream

class Game:
    def __init__(self):
        pg.init()
        pg.mouse.set_visible(False)
        self.screen = pg.display.set_mode(RES)
        pg.event.set_grab(True)
        self.clock = pg.time.Clock()
        self.delta_time = 1
        self.global_trigger = False
        self.global_event = pg.USEREVENT + 0
        pg.time.set_timer(self.global_event, 40)
        self.loading_font = pg.font.Font("resources/font.ttf", 36)
        self.just_blocked_loading = False
        self.room_transition_cooldown_until = 0
        self.new_game()

    def new_game(self):
        self.room_transition_cooldown_until = 0
        self.artwork_stream = ArtworkStream(
            base_url=GALLERY_URL,
            pagination_format=GALLERY_PAGINATION_FORMAT,
            start_page=GALLERY_START_PAGE,
        )
        artworks = self.artwork_stream.load_next_batch(
            target_images=GALLERY_BATCH_SIZE,
            max_pages_per_batch=GALLERY_MAX_PAGES_PER_BATCH,
        )
        self.map = Map(self, len(artworks))
        self.player = Player(self)
        self.object_renderer = ObjectRenderer(self, artworks)
        self.raycasting = RayCasting(self)
        self.object_handler = ObjectHandler(self)
        self.weapon = Weapon(self)
        self.sound = Sound(self)
        pg.mixer.music.play(-1)

    def maybe_transition_room(self):
        now = pg.time.get_ticks()
        if now < self.room_transition_cooldown_until:
            return

        px, py = self.player.pos
        if not (2.0 <= py < 3.0):
            return

        if px <= 1.15:
            entered_side = 'west'
        elif px >= self.map.cols - 2.15:
            entered_side = 'east'
        else:
            return

        self.just_blocked_loading = True
        self.draw_loading_overlay()
        pg.event.pump()
        artworks = self.artwork_stream.load_next_batch(
            target_images=GALLERY_BATCH_SIZE,
            max_pages_per_batch=GALLERY_MAX_PAGES_PER_BATCH,
        )
        if not artworks:
            self.reset_after_blocking_load()
            self.room_transition_cooldown_until = pg.time.get_ticks() + ROOM_TRANSITION_COOLDOWN_MS
            return

        self.object_renderer.set_artworks(artworks)
        self.map.set_artwork_count(len(artworks))
        self.raycasting.textures = self.object_renderer.wall_textures
        self.teleport_to_opposite_door(entered_side)
        self.reset_after_blocking_load()
        self.room_transition_cooldown_until = pg.time.get_ticks() + ROOM_TRANSITION_COOLDOWN_MS

    def teleport_to_opposite_door(self, entered_side: str):
        west_spawn_x = min(3.5, self.map.cols - 2.5)
        east_spawn_x = max(1.5, self.map.cols - 4.5)

        if entered_side == 'east':
            self.player.x = west_spawn_x
            self.player.angle = 0
        else:
            self.player.x = east_spawn_x
            self.player.angle = math.pi

        self.player.y = 2.5

    def reset_after_blocking_load(self):
        self.delta_time = 1
        self.player.rel = 0
        pg.mouse.set_pos([HALF_WIDTH, HALF_HEIGHT])
        pg.event.clear(pg.MOUSEMOTION)
        pg.mouse.get_rel()

    def draw_loading_overlay(self):
        self.object_renderer.draw()
        self.weapon.draw()

        overlay = pg.Surface(RES, pg.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        label = self.loading_font.render('nacitani...', True, (255, 255, 255))
        label_rect = label.get_rect(center=(HALF_WIDTH, HALF_HEIGHT))
        self.screen.blit(label, label_rect)
        pg.display.flip()

    def update(self):
        self.player.update()
        self.maybe_transition_room()
        self.raycasting.update()
        self.object_handler.update()
        self.weapon.update()
        pg.display.flip()
        self.delta_time = self.clock.tick(FPS)
        if self.just_blocked_loading:
            self.delta_time = 1
            self.just_blocked_loading = False
        pg.display.set_caption(f'{self.clock.get_fps() :.1f}')

    def draw(self):
        # self.screen.fill('black')
        self.object_renderer.draw()
        self.weapon.draw()
        # self.map.draw()
        # self.player.draw()

    def check_events(self):
        self.global_trigger = False
        for event in pg.event.get():
            if event.type == pg.QUIT or (event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE):
                pg.quit()
                sys.exit()
            elif event.type == self.global_event:
                self.global_trigger = True
            self.player.single_fire_event(event)

    def run(self):
        while True:
            self.check_events()
            self.update()
            self.draw()


if __name__ == '__main__':
    game = Game()
    game.run()
