import math
from entities.agents import TERRITORY_RADIUS

class Context:
    def __init__(self):
        pass

    def build_context(agent, all_agents, game_map):
        ax, ay = agent.get_tile_pos()
        vision = agent.vision
        hx, hy = agent.home_anchor

        nearest_enemy = None
        nearest_enemy_dist = float("inf")
        nearest_ally = None
        food_pos = None

        for other in all_agents:
            if other is agent or not other.alive:
                continue

            ox, oy = other.get_tile_pos()
            dist = math.hypot(ax - ox, ay - oy)

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

        # Scan for food
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