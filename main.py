from pathlib import Path

import pygame

from entities.spawning import SpawnEntities
from systems.context_builder import Context
from systems.render_debugInfo import Debug
from world.map_generator import Map


PROJECT_ROOT = Path(__file__).resolve().parent
WINDOW_SIZE = (1280, 640)
FPS = 60
BACKGROUND_COLOR = (12, 12, 12)
TEXT_COLOR = (210, 210, 210)
OVERLAY_COLOR = (18, 18, 18)


class Game:
    def __init__(self, window_size=WINDOW_SIZE, fps=FPS):
        pygame.init()
        pygame.font.init()

        self.width, self.height = window_size
        self.fps = fps
        self.screen = pygame.display.set_mode(
            window_size,
            pygame.HWSURFACE | pygame.DOUBLEBUF,
        )
        pygame.display.set_caption("AutonomousWarfare")

        self.clock = pygame.time.Clock()
        self.debug_font = pygame.font.SysFont(None, 15)
        self.status_font = pygame.font.SysFont(None, 19)
        self.spawner = SpawnEntities()
        self.debug = Debug()
        self.debug_mode = False
        self.paused = False
        self.running = True
        self.dragging = False
        self.last_mouse = (0, 0)

        self._init_world()

    def _init_world(self):
        self.game_map = Map(self.width, self.height)
        self.game_map.generate_map()

        entity_assets = self.spawner.load_entity_assets(PROJECT_ROOT / "assets")
        self.agents, self.anchors = self.spawner.spawn_all_agents(
            self.game_map,
            entity_assets,
        )

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)
            elif event.type == pygame.MOUSEWHEEL:
                self.game_map.zoom_at(
                    pygame.mouse.get_pos(), event.y, self.width, self.height
                )
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.dragging = True
                self.last_mouse = event.pos
                tile = self.game_map.get_tile(event.pos)
                if tile is not None:
                    print(tile)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.dragging = False
            elif event.type == pygame.MOUSEMOTION and self.dragging:
                mouse_x, mouse_y = event.pos
                dx = mouse_x - self.last_mouse[0]
                dy = mouse_y - self.last_mouse[1]
                self.game_map.camera_offset -= pygame.Vector2(dx, dy)
                self.game_map.clamp_camera(self.width, self.height)
                self.last_mouse = event.pos

    def _handle_keydown(self, key):
        if key == pygame.K_d:
            self.debug_mode = not self.debug_mode
        elif key == pygame.K_p:
            self.paused = not self.paused
        elif key == pygame.K_r:
            self._init_world()

    def update(self, dt, now):
        if self.paused:
            return

        alive_agents = [agent for agent in self.agents if agent.alive]
        for agent in alive_agents:
            context = Context.build_context(agent, alive_agents, self.game_map)
            agent.update(context, dt, now)

        self.agents = [agent for agent in alive_agents if agent.alive]

    def render(self):
        self.screen.fill(BACKGROUND_COLOR)
        self.game_map.draw(self.screen)
        self.spawner.draw_agents_sorted(self.screen, self.agents)

        if self.debug_mode:
            self.debug.draw_debug(
                self.screen, self.agents, self.anchors, self.game_map
            )
            self.game_map.paint_explored_tiles(
                self.screen,
                self.game_map.camera_offset,
                self.game_map.zoom_factor,
            )

        self.debug.draw_sidebar(
            self.screen, self.agents, self.debug_font, self.width
        )
        self._draw_status()
        pygame.display.flip()

    def _draw_status(self):
        status = self.status_font.render(
            f"Agents: {len(self.agents)} [D] debug [P] pause [R] reset",
            True,
            TEXT_COLOR,
            OVERLAY_COLOR,
        )
        self.screen.blit(status, (10, self.height - 22))

        if self.paused:
            paused = self.status_font.render(
                "PAUSED", True, (255, 215, 0), OVERLAY_COLOR
            )
            self.screen.blit(
                paused,
                paused.get_rect(center=(self.width // 2, self.height // 2)),
            )

    def run(self):
        try:
            while self.running:
                dt = self.clock.tick(self.fps)
                now = pygame.time.get_ticks()
                self._handle_events()
                if self.running:
                    self.update(dt, now)
                    self.render()
        finally:
            pygame.quit()


if __name__ == "__main__":
    game = Game()
    game.run()
