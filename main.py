import pygame
import random
import math
from pathlib import Path

from map_generator import Map
from agents import make_agent, UNIT_STATS, TERRITORY_RADIUS

pygame.init()
pygame.font.init()

DEBUG_FONT  = pygame.font.SysFont(None, 15)
STATUS_FONT = pygame.font.SysFont(None, 19)

TEAMS      = [1, 2, 3, 4]
ARMY_TYPES = list(UNIT_STATS.keys())
SPAWN_PER_TYPE  = 2     # agents per unit type per team at startup

TEAM_COLORS = {
    1: (220, 60,  60),
    2: (60,  120, 220),
    3: (60,  200, 80),
    4: (220, 180, 30),
}


# asset loader
def load_entity_assets(asset_dir="assets"):
    assets = {}
    for f in sorted(Path(asset_dir).iterdir()):
        if not f.is_file() or not f.name.lower().startswith("entity-army-"):
            continue
        parts = f.stem.split("-")           # entity / army / archer / team1
        if len(parts) < 4:
            continue
        unit_type = parts[2]
        try:
            team_num = int(parts[3].replace("team", ""))
            img      = pygame.image.load(str(f)).convert_alpha()
        except Exception:
            continue
        assets.setdefault(unit_type, {})[team_num] = img
    return assets


# spawning
def _pick_anchor(game_map, existing, min_sep):
    # Returns a walkable grassland tile at least min_sep tiles from every existing anchor.
    for _ in range(500):
        x = random.randint(3, game_map.cols - 4)
        y = random.randint(3, game_map.rows - 4)
        t = game_map.get_tile_at(x, y)
        if not t or not t.walkable:
            continue
        if t.biom not in ("grassland", "shore"):
            continue
        if all(math.hypot(x - ax, y - ay) >= min_sep for ax, ay in existing):
            return (x, y)
    return None


def spawn_all_agents(game_map, entity_assets):
    agents  = []
    anchors = {}          # team → (tx, ty)
    placed  = []

    # Space teams evenly; minimum gap scales with map dimensions
    min_sep = min(game_map.cols, game_map.rows) // 2

    for team in TEAMS:
        anchor = _pick_anchor(game_map, placed, min_sep)
        if anchor is None:
            # Relax constraint if map is very dense
            anchor = _pick_anchor(game_map, placed, min_sep // 2)
        if anchor is None:
            for _ in range(300):
                x = random.randint(0, game_map.cols - 1)
                y = random.randint(0, game_map.rows - 1)
                if game_map.is_walkable(x, y):
                    anchor = (x, y)
                    break
        if anchor is None:
            anchor = (game_map.cols // 2, game_map.rows // 2)

        anchors[team] = anchor
        placed.append(anchor)

        ox, oy = anchor

        for unit_type in ARMY_TYPES:
            imgs = entity_assets.get(unit_type, {})
            img  = imgs.get(team) or imgs.get(1)
            if img is None:
                img = pygame.Surface((16, 16), pygame.SRCALPHA)
                img.fill((*TEAM_COLORS.get(team, (180, 180, 180)), 255))

            for _ in range(SPAWN_PER_TYPE):
                for attempt in range(60):
                    tx = ox + random.randint(-6, 6)
                    ty = oy + random.randint(-6, 6)
                    tx = max(0, min(game_map.cols - 1, tx))
                    ty = max(0, min(game_map.rows - 1, ty))
                    if game_map.is_walkable(tx, ty):
                        break
                else:
                    tx, ty = ox, oy

                px = tx * game_map.tile_size
                py = ty * game_map.tile_size
                agents.append(make_agent(unit_type, px, py, img, game_map, team, anchor))

    return agents, anchors


# ── z-sorted drawing ──────────────────────────────────────────────────────────

def draw_agents_sorted(screen, agents, game_map):
    # Sort agents by their Y pixel position so southern (lower) agents
    # draw on top of northern ones, matching the tile painter's order.
    # This makes agents walking behind trees disappear correctly because
    # the map is also drawn top-to-bottom row by row.
    for agent in sorted(agents, key=lambda a: a.y):
        agent.draw(screen)


# ── context builder ───────────────────────────────────────────────────────────

def build_context(agent, all_agents, game_map):
    ax, ay = agent.get_tile_pos()
    vision = agent.vision
    hx, hy = agent.home_anchor

    nearest_enemy      = None
    nearest_enemy_dist = float("inf")
    nearest_ally       = None
    food_pos           = None

    for other in all_agents:
        if other is agent or not other.alive:
            continue
        ox, oy = other.get_tile_pos()
        dist   = math.hypot(ax - ox, ay - oy)

        if other.team != agent.team:
            # Enemy is "in territory" if it's within vision range AND within
            # TERRITORY_RADIUS tiles of this team's home anchor.
            enemy_in_home = math.hypot(ox - hx, oy - hy) <= TERRITORY_RADIUS
            if dist <= vision and enemy_in_home and dist < nearest_enemy_dist:
                nearest_enemy      = other
                nearest_enemy_dist = dist
        else:
            if dist <= 4 and other.hunger <= 2.0 and agent.inventory.count("food") > 1:
                nearest_ally = other

    # Food tile scan (placeholder; wire up animals/bushes here later)
    for r in range(1, min(vision, 8) + 1):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                t = game_map.get_tile_at(ax + dx, ay + dy)
                if t and t.biom == "food":
                    food_pos = (ax + dx, ay + dy)
        if food_pos:
            break

    return {
        "enemy_in_territory": nearest_enemy is not None,
        "enemy_pos":          nearest_enemy.get_tile_pos() if nearest_enemy else None,
        "enemy_ref":          nearest_enemy,
        "ally_trading":       nearest_ally is not None,
        "ally_pos":           nearest_ally.get_tile_pos() if nearest_ally else None,
        "food_pos":           food_pos,
    }


# ── debug overlay ─────────────────────────────────────────────────────────────

def draw_debug(screen, agents, anchors, game_map):
    ts   = game_map.tile_size
    zoom = game_map.zoom_factor
    cam  = game_map.camera_offset

    # Territory circles (one per team)
    for team, (hx, hy) in anchors.items():
        color = TEAM_COLORS.get(team, (255, 255, 255))
        sx = int(hx * ts * zoom - cam.x + ts * zoom / 2)
        sy = int(hy * ts * zoom - cam.y + ts * zoom / 2)
        r  = int(TERRITORY_RADIUS * ts * zoom)
        pygame.draw.circle(screen, (*color, 30), (sx, sy), r, 1)

    for agent in agents:
        if not agent.alive:
            continue
        color  = TEAM_COLORS.get(agent.team, (255, 255, 255))
        ax, ay = agent.get_tile_pos()

        if agent.path:
            pts = [(int(tx * ts * zoom - cam.x), int(ty * ts * zoom - cam.y))
                   for tx, ty in agent.path]
            if len(pts) > 1:
                pygame.draw.lines(screen, color, False, pts, 1)

        sx = int(ax * ts * zoom - cam.x + ts * zoom / 2)
        sy = int(ay * ts * zoom - cam.y + ts * zoom / 2)
        pygame.draw.circle(screen, color, (sx, sy), int(agent.vision * ts * zoom), 1)


def draw_sidebar(screen, agents, font, sw):
    alive_by_team = {}
    for a in agents:
        if a.alive:
            alive_by_team.setdefault(a.team, []).append(a)

    x, y = sw - 190, 8
    for team in TEAMS:
        color   = TEAM_COLORS.get(team, (255, 255, 255))
        members = alive_by_team.get(team, [])

        screen.blit(font.render(f"Team {team}  {len(members)} alive", True, color, (18,18,18)), (x, y))
        y += 16

        for a in members[:10]:
            pygame.draw.rect(screen, (50, 50, 50), (x, y, 105, 3))
            pygame.draw.rect(screen, color,        (x, y, max(1, int(105 * a.hp / a.max_hp)), 3))
            screen.blit(font.render(f"{a.unit_type[:6]} {a.state[:7]}", True, (185,185,185), (18,18,18)), (x + 110, y - 1))
            y += 7

        if len(members) > 10:
            screen.blit(font.render(f"  +{len(members) - 10} more", True, (120,120,120), (18,18,18)), (x, y))
            y += 9
        y += 5


# ── game ─────────────────────────────────────────────────────────────────────

class Game:
    def __init__(self):
        self.width  = 1280
        self.height = 640

        self.screen = pygame.display.set_mode(
            (self.width, self.height),
            pygame.HWSURFACE | pygame.DOUBLEBUF,
        )
        pygame.display.set_caption("World Simulation")

        self.clock      = pygame.time.Clock()
        self.debug_mode = False
        self.paused     = False

        self._init_world()

    def _init_world(self):
        self.game_map = Map(self.width, self.height)
        self.game_map.generate_map()

        entity_assets        = load_entity_assets()
        self.agents, self.anchors = spawn_all_agents(self.game_map, entity_assets)

    def _handle_events(self, dragging, last_mouse):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False, dragging, last_mouse

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_d:
                    self.debug_mode = not self.debug_mode
                elif event.key == pygame.K_p:
                    self.paused = not self.paused
                elif event.key == pygame.K_r:
                    self._init_world()

            elif event.type == pygame.MOUSEWHEEL:
                self.game_map.zoom_at(pygame.mouse.get_pos(), event.y, self.width, self.height)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                dragging   = True
                last_mouse = pygame.mouse.get_pos()
                t = self.game_map.get_tile(last_mouse)
                if t:
                    print(t)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging = False

            elif event.type == pygame.MOUSEMOTION and dragging:
                mx, my = pygame.mouse.get_pos()
                dx, dy = mx - last_mouse[0], my - last_mouse[1]
                self.game_map.camera_offset -= pygame.Vector2(dx, dy)
                self.game_map.clamp_camera(self.width, self.height)
                last_mouse = (mx, my)

        return True, dragging, last_mouse

    def update(self, dt, now):
        if self.paused:
            return

        alive = [a for a in self.agents if a.alive]
        for agent in alive:
            ctx = build_context(agent, alive, self.game_map)
            agent.update(ctx, dt, now)

        # Combat is now handled inside each agent's try_attack with its own timer,
        # so no separate combat-resolution loop is needed here.

        self.agents = [a for a in self.agents if a.alive]

    def render(self):
        self.screen.fill((12, 12, 12))
        self.game_map.draw(self.screen)

        # Z-sorted so agents behind trees visually disappear under them
        draw_agents_sorted(self.screen, self.agents, self.game_map)

        if self.debug_mode:
            draw_debug(self.screen, self.agents, self.anchors, self.game_map)
            self.game_map.paint_explored_tiles(
                self.screen,
                self.game_map.camera_offset,
                self.game_map.zoom_factor,
            )

        draw_sidebar(self.screen, self.agents, DEBUG_FONT, self.width)

        alive_count = sum(1 for a in self.agents if a.alive)
        self.screen.blit(
            STATUS_FONT.render(
                f"Agents: {alive_count}    [D] debug    [P] pause    [R] reset",
                True, (210, 210, 210), (18, 18, 18),
            ),
            (10, self.height - 22),
        )

        if self.paused:
            self.screen.blit(
                STATUS_FONT.render("PAUSED", True, (255, 215, 0), (18, 18, 18)),
                (self.width // 2 - 28, self.height // 2),
            )

        pygame.display.flip()

    def run(self):
        dragging, last_mouse = False, (0, 0)
        while True:
            dt  = self.clock.tick(60)
            now = pygame.time.get_ticks()

            running, dragging, last_mouse = self._handle_events(dragging, last_mouse)
            if not running:
                break

            self.update(dt, now)
            self.render()

        pygame.quit()


if __name__ == "__main__":
    Game().run()