import pygame
import random
import math
import yaml
from collections import deque
from pathFinding import AStar


# Load configurations
with open("game.yaml", "r") as f:
    config = yaml.safe_load(f)

UNIT_STATS = config["unit_stats"]
AGENT = config["agent"]
VISION_BIOME = config["vision_biome"]
NEEDS = config["needs"]
DURATIONS = config["durations"]
INVENTORY = config["inventory"]
TERRITORY_RADIUS = config["territory"].get("radius")


# Inventory logic
class Inventory:
    def __init__(self, slots=INVENTORY["slots"]):
        self.slots = [None] * slots # Initialize N empty Slots

    # Add item in the inventory
    def add(self, item, qty=1):
        for slot in self.slots:
            if slot and slot['item'] == item:
                slot['qty'] += 1
                return True
        for i, slot in enumerate(self.slots):
            if slot is None:
                self.slots[i] = {"item": item, "qty": qty}
                return True
        
        return False
    # Remove item from the inventory
    def remove(self, item, qty=1):
        for i, slot in enumerate(self.slots):
            if slot and slot['item'] == item:
                slot['qty'] -= qty
                if slot['qty'] <= 0:
                    self.slots[i] = None
                return True
        return False
    
    def count(self, item):
        for slot in self.slots:
            if slot and slot["item"] == item:
                return slot["qty"]
        return 0

    def is_full(self):
        return all(s is not None for s in self.slots)

    def __repr__(self):
        return str([s for s in self.slots if s])
        
# Base Agent Class logic
class Agent:
    def __init__(self, x, y, image, map_ref, unit_type, team, home_anchor):
        self.x = x
        self.y = y
        self.image = image
        self.map = map_ref
        self.unit_type = unit_type
        self.team = team
        self.home_anchor = home_anchor   # (tx, ty) – team spawn centre

        unit = UNIT_STATS[unit_type]
        self.max_hp = unit["hp"]
        self.hp = float(unit["hp"])
        self.attack = unit["attack"]
        self.defense = unit["defense"]
        self.base_speed = unit["speed"]
        self.attack_range = unit["range"]
        self.is_melee = unit["melee"]
        self._base_vision = unit["base_vision"]
        self.attack_interval = unit["attack_interval"]

        self.speed = self.base_speed
        self.path = []
        self.state = "idle"

        self.energy = random.uniform(3.5, 5.0)
        self.hunger = random.uniform(3.5, 5.0)
        self.thirst = random.uniform(3.5, 5.0)

        self.recovering = False
        self.drinking = False
        self.drink_timer = 0
        self.adrenaline = False
        self.adrenaline_end = 0
        self.alive = True
        self.age = 0          # ms – used for reproduction gating
        self.can_reproduce = True

        self._last_attack_time = 0       # per-agent swing cooldown

        self.inventory  = Inventory()
        self.pathfinder = AStar(map_ref)
        self.tile_size  = map_ref.tile_size
        self.rect = pygame.Rect(x, y, self.tile_size, self.tile_size)
    
    # Logic for the agent vision
    @property
    def vision(self):
        tx, ty = self.get_tile_pos()
        tile = self.map.get_tile_at(tx, ty)
        biome = tile.biom if tile else "grassland"
        bion_vis = VISION_BIOME[biome]
        mult = bion_vis if bion_vis else 1.0
        return max(2, int(self._base_vision * mult))
    
    def draw(self, screen):
        zoom_f = self.map.zoom_factor
        cam = self.map.camera_offset
        size = max(2, int(AGENT["size"] * zoom_f))

        # center within tile
        tile_px = self.tile_size * zoom_f
        off = int((tile_px - size) / 2)

        sx = int(self.x * zoom_f - cam.x) + off
        sy = int(self.y * zoom_f - cam.y) + off

        screen.blit(pygame.transform.scale(self.image, (size, size)), (sx, sy))
        self._draw_bars(screen, sx, sy, size)

    # Draw bars for agent stats like hunger, thirst, hp
    def _draw_bars(self, screen, sx, sy, sz):
        def bar(val, max_val, color, off_y):
            w = max(1, int(sz * (val / max_val)))
            pygame.draw.rect(screen, (35, 35, 35), (sx, sy - off_y, sz, 2))
            pygame.draw.rect(screen, color, (sx, sy - off_y,  w, 2))

        bar(self.hp, self.max_hp, (210, 40, 40), 9)
        bar(self.hunger, 5.0, (220, 150, 20), 6)
        bar(self.thirst, 5.0, (40, 120, 210), 3)
    
    def move_along_path(self):
        if not self.path or self.drinking or self.recovering:
            return
        
        tx, ty = self.path[0]
        px, py = tx * self.tile_size, ty * self.tile_size
        dx, dy = px - self.x, py - self.y
        dist = math.hypot(dx, dy)

        if dist <= self.speed:
            self.x, self.y = float(px), float(py)
            self.path.pop(0)
        elif dist > 0:
            self.x += self.speed * dx / dist
            self.y += self.speed * dy / dist
        
        self.rect.topleft = (int(self.x), int(self.y))
    
    def get_tile_pos(self):
        return int(self.x // self.tile_size), int(self.y // self.tile_size)
    
    def set_path(self, path):
        self.path = path
    
    def _update_needs(self, dt):
        self.age += dt

        if self.path:
            self.energy = max(0.0, self.energy - NEEDS["energy_drain"])
            self.hunger = max(0.0, self.hunger - NEEDS["energy_drain"])
            self.thirst = max(0.0, self.thirst - NEEDS["thirst_decay"])
        
        else:
            self.energy = min(5.0, self.energy + NEEDS["energy_regen"])
        
        if self.energy <= 0.1 and not self.recovering:
            self.recovering = True
            self.speed = 0
            self.path.clear()
        
        if self.recovering and self.energy >= 4.5:
            self.recovering = False
            self.speed = self.base_speed
        
        if self.hunger == 0.0:
            self.hp = max(0.0, self.hp - NEEDS["starvation_dmg"])
        
        if self.thirst == 0.0:
            self.hp = max(0.0, self.hp - NEEDS["dehydrate_dmg"])
        
        if self.hp <= 0.0:
            self.alive = False
    
    def _trigger_adrenaline(self, now):
        self.adrenaline = True
        self.adrenaline_end = now + DURATIONS["adrenaline"]
        # Temporarily suppress hunger signal for the flee window
        self.hunger = min(5.0, self.hunger + 0.8)

    def _check_adrenaline(self, now):
        if self.adrenaline and now >= self.adrenaline_end:
            self.adrenaline = False
            self.speed = self.base_speed
    
    def decision_maker(self, context):
        if not self.alive:
            return "dead"
        if self.recovering:
            return "rest"
        if context.get("enemy_in_territory"):
            return self._threat_response(context)
        if self.thirst <= NEEDS["thirst_crit"]:
            return "drink"
        if self.hunger <= NEEDS["hunger_crit"]:
            return "eat"
        if context.get("ally_trading"):
            return "trade"
        
        return "explore"
    
    def _threat_response(self, context):
        # Default: flee. Subclasses override for combat.
        return "flee"

    def execute(self, action, context, now):
        if action == "dead":
            self.path.clear() 
            self.speed = 0 
            return

        if action == "rest":
            self.state = "resting"
            return

        if action == "drink":
            self.state = "drinking"
            self._seek_water(now, context)
            return

        if action == "eat":
            self.state = "eating"
            self._seek_food(context)
            return

        if action == "flee":
            self.state  = "fleeing"
            self.speed  = min(self.base_speed * 1.6, self.base_speed + 0.15)
            self._flee(context["enemy_pos"])
            return

        if action == "trade":
            self.state = "trading"
            self._trade(context["ally_pos"])
            return

        if action == "explore":
            self.state = "exploring"
            self._explore()
        
    def _seek_water(self, now, context):
        if self.drinking:
            if context.get("enemy_in_territory"):
                self.drinking = False
                self.speed = self.base_speed
                return
            if now >= self.drink_timer:
                self.thirst = 5.0
                self.drinking = False
                self.speed = self.base_speed
                return
        water = self._nearest_tile("lake")
        if water:
            cx, cy = self.get_tile_pos()
            if math.hypot(cx - water[0], cy - water[1]) <= 1.5:
                self.path.clear()
                self.drinking = True
                self.drink_timer = now + DURATIONS["drink"]
                self.speed = 0
            else:
                self._move_to(water)
    
    def _seek_food(self, context):
        if self.inventory.count("food") > 0:
            self.inventory.remove("food")
            self.hunger = 5.0
            return
        
        food = context.get("food_pos")
        if food:
            self._move_to(food)
    
    def _flee(self, enemy_pos):
        if self.path:
            return
        
        cx, cy = self.get_tile_pos()
        dx, dy = cx - enemy_pos[0], cy - enemy_pos[1]
        length = math.hypot(dx, dy) or 1
        tx = max(0, min(self.map.cols - 1, int(cx + (dx / length) * 10)))
        ty = max(0, min(self.map.rows - 1, int(cy + (dy / length) * 10)))
        if self.map.is_walkable(tx, ty):
            self._move_to((tx, ty))
    
    def _explore(self):
        if self.path:
            return
        
        cx, cy = self.get_tile_pos()
        hx, hy = self.home_anchor

        for _ in range(10):
            # pick a tile within 20 tiles of home anchor
            tx = hx + random.randint(-20, 20)
            ty = hy + random.randint(-20, 20)

            tx = max(0, min(self.map.cols - 1, tx))
            ty = max(0, min(self.map.rows - 1, ty))
            if self.map.is_walkable(tx, ty):
                path = self.pathfinder.find_path((cx, cy), (tx, ty))
                if path:
                    self.set_path(path)
                    return
    
    def _trade(self, ally_pos):
        cx, cy = self.get_tile_pos()
        distance_between_agetns = math.hypot(cx - ally_pos[0], cy - ally_pos[1])
        if distance_between_agetns <= 2:
            if self.inventory.count("food") > 1:
                self.inventory.remove("food") # add a way so the ally actually recives the item
        else:
            self._move_to(ally_pos)

    def _move_to(self, tile_pos):
        if self.path and self.path[-1] == tile_pos:
            return
        
        cx, cy = self.get_tile_pos()
        path = self.pathfinder.find_path((cx, cy), tile_pos)
        if path:
            self.set_path(path)
    
    def _nearest_tile(self, biom):
        # optimized bfs search for the nearest tile
        cx, cy = self.get_tile_pos()
        limit = self.vision * 4
        visited = set([(cx, cy)])
        queue = deque([(cx, cy, 0)])
        cols, rows = self.map.cols, self.map.rows

        while queue:
            x, y, d = queue.popleft()
            if d > limit:
                continue

            t = self.map.get_tile_at(x, y)
            if t and t.biom == biom:
                return (x, y)

            for nx, ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if 0 <= nx < cols and 0 <= ny < rows and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append((nx, ny, d + 1))
        
        return None

    def can_attack(self, other):
        if not other.alive or other.team == self.team:
            return False
        
        cx, cy = self.get_tile_pos()
        ox, oy = other.get_tile_pos()

        return math.hypot(cx - ox, cy - oy) <= self.attack_range
    
    def try_attack(self, other, now):
        if not self.can_attack(other):
            return False
        
        if now - self._last_attack_time < self.attack_interval:
            return False

        damage = max(1, self.attack - other.defense // 2)
        other.hp = max(0.0, other.hp - damage)

        if other.hp <= 0:
            other.alive = False
        self._last_attack_time = now
        return True

    def update(self, context, dt, now):
        if not self.alive:
            return
        
        self._update_needs(dt)
        self._check_adrenaline(now)

        if context.get("enemy_in_territory") and self.hunger <= NEEDS["hunger_crit"]:
            self._trigger_adrenaline(now)
        
        action = self.decision_maker(context)
        self.execute(action, context, now)
        self.move_along_path()
    
    def __repr__(self):
        return f"<{self.unit_type} T={self.team} hp={self.hp:.0f} {self.state}>"

# Subclasses
class Archer(Agent):
    # Archers engage from range and reposition to stay at ideal distance
    def _threat_response(self, context):
        ep = context["enemy_pos"]
        cx, cy = self.get_tile_pos()

        distance = math.hypot(cx - ep[0], cy - ep[1])
        return "attack" if distance <= self.attack_range else "reposition"
    
    def execute(self, action, context, now):
        if action == "attack":
            self.state = "attacking"
            e = context.get("enemy_ref")
            if e:
                self.try_attack(e, now)
        elif action == "reposition":
            self.state = "repositioning"
            self._keep_range(context["enemy_pos"])
        else:
            super().execute(action, context, now)

    def _keep_range(self, ep):
        cx, cy = self.get_tile_pos()
        dx, dy = cx - ep[0], cy - ep[1]
        length = math.hypot(dx, dy) or 1
        ideal  = self.attack_range - 1
        tx = max(0, min(self.map.cols - 1, int(ep[0] + (dx / length) * ideal)))
        ty = max(0, min(self.map.rows - 1, int(ep[1] + (dy / length) * ideal)))
        self._move_to((tx, ty))
    
class MeleeUnit(Agent):
    # Melee units close in and fight only when adjacent
    def _threat_response(self, context):
        return "attack"

    def execute(self, action, context, now):
        if action == "attack":
            self.state = "attacking"
            e = context.get("enemy_ref")
            if e:
                if self.can_attack(e):
                    self.try_attack(e, now)
                else:
                    self._move_to(e.get_tile_pos())
        else:
            super().execute(action, context, now)

class Villager(Agent):
    # Only fights when cornered on the same tile, otherwise always flees
    def _threat_response(self, context):
        return "fight_back" if self.get_tile_pos() == tuple(context["enemy_pos"]) else "flee"

    def execute(self, action, context, now):
        if action == "fight_back":
            self.state = "fighting"
            e = context.get("enemy_ref")
            if e:
                self.try_attack(e, now)
        else:
            super().execute(action, context, now)

def make_agent(unit_type, x, y, image, map_ref, team, home_anchor):
    cls = Archer if unit_type == "archer" else \
          Villager if unit_type == "villager" else \
          MeleeUnit
    return cls(x, y, image, map_ref, unit_type, team, home_anchor)