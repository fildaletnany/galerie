import pygame as pg
import sys
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
        self.new_game()

    def new_game(self):
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

    def maybe_extend_gallery(self):
        if self.artwork_stream.exhausted:
            return
        if self.player.x < (self.map.cols - GALLERY_LOAD_AHEAD_TILES):
            return

        self.draw_loading_overlay()
        pg.event.pump()
        artworks = self.artwork_stream.load_next_batch(
            target_images=GALLERY_BATCH_SIZE,
            max_pages_per_batch=GALLERY_MAX_PAGES_PER_BATCH,
        )
        if not artworks:
            self.delta_time = 1
            self.player.rel = 0
            return

        self.object_renderer.add_artworks(artworks)
        total_artworks = self.artwork_stream.next_texture_id - ARTWORK_FIRST_TEXTURE_ID
        self.map.set_artwork_count(total_artworks)
        # Prevent a large delta_time step after blocking I/O from moving the player unexpectedly.
        self.delta_time = 1
        self.player.rel = 0
        pg.mouse.get_rel()

    def draw_loading_overlay(self):
        self.object_renderer.draw()
        self.weapon.draw()

        overlay = pg.Surface(RES, pg.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        label = self.loading_font.render('Loading...', True, (255, 255, 255))
        label_rect = label.get_rect(center=(HALF_WIDTH, HALF_HEIGHT))
        self.screen.blit(label, label_rect)
        pg.display.flip()

    def update(self):
        self.player.update()
        self.maybe_extend_gallery()
        self.raycasting.update()
        self.object_handler.update()
        self.weapon.update()
        pg.display.flip()
        self.delta_time = self.clock.tick(FPS)
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
