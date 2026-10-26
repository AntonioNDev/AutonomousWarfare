import pygame
from entities.spawning import TEAM_COLORS, TEAMS
from entities.agents import TERRITORY_RADIUS

class Debug:
    def draw_debug(self, screen, agents, anchors, game_map):
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

    def draw_sidebar(self, screen, agents, font, sw):
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