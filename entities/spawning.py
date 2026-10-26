import random
from pathlib import Path
import pygame
from entities.agents import make_agent, UNIT_STATS
import math

TEAM_COLORS = {
        1: (220, 60,  60),
        2: (60,  120, 220),
        3: (60,  200, 80),
        4: (220, 180, 30),
    }
TEAMS = [1, 2, 3, 4]

class SpawnEntities:
    def __init__(self):
        self.ARMY_TYPES = list(UNIT_STATS.keys())
        self.SPAWN_PER_TYPE = 2 # agents per unit

    # SPAWN AGENTS 
    def load_entity_assets(self, asset_dir="assets"):
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
                img = pygame.image.load(str(f)).convert_alpha()
            except Exception:
                continue
            assets.setdefault(unit_type, {})[team_num] = img
        return assets

    def _pick_anchor(self, game_map, existing, min_sep):
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

    def spawn_all_agents(self, game_map, entity_assets):
        agents  = []
        anchors = {}          # team → (tx, ty)
        placed  = []

        # Space teams evenly; minimum gap scales with map dimensions
        min_sep = min(game_map.cols, game_map.rows) // 2

        for team in TEAMS:
            anchor = self._pick_anchor(game_map, placed, min_sep)
            if anchor is None:
                # Relax constraint if map is very dense
                anchor = self._pick_anchor(game_map, placed, min_sep // 2)
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

            for unit_type in self.ARMY_TYPES:
                imgs = entity_assets.get(unit_type, {})
                img  = imgs.get(team) or imgs.get(1)
                if img is None:
                    img = pygame.Surface((16, 16), pygame.SRCALPHA)
                    img.fill((*TEAM_COLORS.get(team, (180, 180, 180)), 255))

                for _ in range(self.SPAWN_PER_TYPE):
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
    
    def draw_agents_sorted(self, screen, agents):
        for agent in sorted(agents, key=lambda a: a.y):
            agent.draw(screen)
    # ----