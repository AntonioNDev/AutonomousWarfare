import pygame
import random
import json
import math
from pathlib import Path
from noise import pnoise2
from collections import deque

# Load assets
def _load_assets(asset_dir="assets", tile_size=16):
   # Returns pre-scaled surfaces sorted into named buckets.
   # Only oak and darkpine trees are active; others are loaded but unused until weather system.
   buckets = {
      "grass":         [],
      "water_deep":    [],
      "water_shallow": [],
      "water_coast":   [],
      "sand":          [],
      "trees":         {"oak": [], "darkpine": []},
      "rocks":         [],
      "mountain_peak": [],
      "mountain_rock": [],
   }

   def s(img):
      return pygame.transform.scale(img, (tile_size, tile_size))

   for f in sorted(Path(asset_dir).iterdir()):
      if not f.is_file():
         continue
      try:
         img = pygame.image.load(str(f)).convert_alpha()
      except Exception:
         continue

      name = f.name.lower()

      if "grass" in name:
         buckets["grass"].append(s(img))
      elif "deepwater" in name:
         buckets["water_deep"].append(s(img))
      elif "shallowwater" in name:
         buckets["water_shallow"].append(s(img))
      elif "oastwater" in name:
         buckets["water_coast"].append(s(img))
      elif "sand" in name:
         buckets["sand"].append(s(img))
      elif "mountain" in name and "rock" in name:
         buckets["mountain_rock"].append(s(img))
      elif "mountain" in name:
         buckets["mountain_peak"].append(s(img))
      elif "rock" in name:
         buckets["rocks"].append(s(img))
      elif "tree" in name:
         if "oak" in name:
               buckets["trees"]["oak"].append(s(img))
         elif "darkpine" in name:
               buckets["trees"]["darkpine"].append(s(img))

   # Solid-colour fallbacks so the game never crashes on missing assets
   def fb(color):
      surf = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
      surf.fill((*color, 255))
      return surf

   if not buckets["grass"]:         buckets["grass"]         = [fb((100, 140, 60))]
   if not buckets["water_deep"]:    buckets["water_deep"]    = [fb((20, 60, 120))]
   if not buckets["water_shallow"]: buckets["water_shallow"] = [fb((60, 120, 180))]
   if not buckets["water_coast"]:   buckets["water_coast"]   = [fb((100, 160, 200))]
   if not buckets["sand"]:          buckets["sand"]          = [fb((210, 190, 130))]
   if not buckets["rocks"]:         buckets["rocks"]         = [fb((120, 110, 90))]
   if not buckets["mountain_peak"]: buckets["mountain_peak"] = [fb((160, 160, 160))]
   if not buckets["mountain_rock"]: buckets["mountain_rock"] = [fb((130, 120, 100))]
   if not buckets["trees"]["oak"]:      buckets["trees"]["oak"]     = [fb((30, 90, 30))]
   if not buckets["trees"]["darkpine"]: buckets["trees"]["darkpine"]= [fb((20, 60, 20))]

   return buckets

# Tile class
class Tile:
   # bg_surface is always the ground (grass/sand/water).
   # top_surface is the overlay (tree/rock/mountain) or None.
   # render_offset shifts the top_surface for tall sprites.
   __slots__ = (
      "x", "y", "size",
      "bg_surface", "top_surface",
      "obstacle", "walkable", "biom",
      "explored", "render_offset",
   )

   def __init__(self, x, y, size, bg=None, top=None,
               obstacle=None, walkable=True, biom="grassland"):
      self.x = x
      self.y = y
      self.size = size
      self.bg_surface  = bg
      self.top_surface = top
      self.obstacle  = obstacle
      self.walkable  = walkable
      self.biom      = biom
      self.explored  = False
      self.render_offset = pygame.Vector2(0, 0)

   def draw(self, screen):
      px = self.x * self.size
      py = self.y * self.size
      if self.bg_surface:
         screen.blit(self.bg_surface, (px, py))
      if self.top_surface:
         screen.blit(self.top_surface, (px + self.render_offset.x, py + self.render_offset.y))

   # Mutation helpers – each resets all relevant fields so nothing is left stale.

   def place_tree(self, surf):
      self.top_surface  = surf
      self.obstacle     = "tree"
      self.walkable     = True
      self.render_offset = pygame.Vector2(0, -self.size // 2)

   def remove_tree(self):
      self.top_surface  = None
      self.obstacle     = None
      self.walkable     = True
      self.render_offset = pygame.Vector2(0, 0)

   def place_rock(self, surf):
      self.top_surface  = surf
      self.obstacle     = "rock"
      self.walkable     = False
      self.render_offset = pygame.Vector2(0, 0)

   def remove_rock(self):
      self.top_surface  = None
      self.obstacle     = None
      self.walkable     = True
      self.render_offset = pygame.Vector2(0, 0)

   def place_mountain_peak(self, surf):
      self.top_surface  = surf
      self.obstacle     = "mountain_peak"
      self.walkable     = False
      self.render_offset = pygame.Vector2(0, 0)

   def place_mountain_rock(self, surf):
      self.top_surface  = surf
      self.obstacle     = "mountain_rock"
      self.walkable     = False
      self.render_offset = pygame.Vector2(0, 0)

   def set_water(self, surf, depth="deep"):
      self.bg_surface   = surf
      self.top_surface  = None
      self.obstacle     = f"water_{depth}"
      self.walkable     = False
      self.biom         = "lake"
      self.render_offset = pygame.Vector2(0, 0)

   def set_sand(self, surf):
      self.bg_surface   = surf
      self.top_surface  = None
      self.obstacle     = None
      self.walkable     = True
      self.biom         = "shore"
      self.render_offset = pygame.Vector2(0, 0)

   def set_grass(self, surf, biom="grassland"):
      self.bg_surface   = surf
      self.top_surface  = None
      self.obstacle     = None
      self.walkable     = True
      self.biom         = biom
      self.render_offset = pygame.Vector2(0, 0)

   def to_dict(self):
      return {
         "x": self.x, "y": self.y,
         "obstacle": self.obstacle,
         "biom": self.biom,
         "explored": self.explored,
         "walkable": self.walkable,
      }

   @staticmethod
   def from_dict(d, size=16):
      t = Tile(d["x"], d["y"], size)
      t.obstacle = d.get("obstacle")
      t.biom     = d.get("biom", "grassland")
      t.explored = d.get("explored", False)
      t.walkable = d.get("walkable", True)
      return t

# CONFIGURATIONS
# Elevation thresholds
_WATER_T  = 0.45   # below → water 0.45
_SAND_T   = 0.48 # water..sand → shore band 0.48
_HIGH_T   = 0.61  # above → highland / mountain candidate 0.61

# Moisture thresholds (within land)
_OAK_T      = 0.60   # moisture above this → oak forest 0.60
_DARKPINE_T = 0.55   # moisture below this → darkpine forest 0.55
# between → open grassland

# Water depth rings (Chebyshev distance to nearest land tile)
_COAST_D   = 1 # 1
_SHALLOW_D = 2 # 2

class Map:
   def __init__(self, width, height, tile_size=16):
      self.width     = width
      self.height    = height
      self.tile_size = tile_size
      self.cols      = width  // tile_size
      self.rows      = height // tile_size

      self.zoom_factor   = 1.0
      self.min_zoom      = 1.0
      self.max_zoom      = 2.8
      self.camera_offset = pygame.Vector2(0, 0)

      # Independent seeds for elevation and moisture so biomes don't mirror terrain
      self._ex = random.uniform(0, 10_000)
      self._ey = random.uniform(0, 10_000)
      self._mx = random.uniform(0, 10_000)
      self._my = random.uniform(0, 10_000)

      self.assets   = _load_assets(tile_size=tile_size)
      self.map_data = [[Tile(x, y, tile_size) for y in range(self.rows)]
                        for x in range(self.cols)]

   def _prune_small_lakes(self, min_size=6, connectivity=4):
      """
      Convert small connected water components (biom == "lake") into land.
      Call this AFTER initial water assignment in generate_map() and BEFORE
      _apply_water_depth() / shore-depth processing.
      """
      cols = self.cols
      rows = self.rows

      visited = [[False] * rows for _ in range(cols)]

      if connectivity == 8:
         neigh = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
      else:
         neigh = [(-1,0),(1,0),(0,-1),(0,1)]

      def is_water(x,y):
         return 0 <= x < cols and 0 <= y < rows and self.map_data[x][y].biom == "lake"

      for x in range(cols):
         for y in range(rows):
            if visited[x][y]:
               continue
            if not is_water(x,y):
               visited[x][y] = True
               continue

            # BFS collect component
            q = deque()
            comp = []
            q.append((x,y))
            visited[x][y] = True

            while q:
               cx, cy = q.popleft()
               comp.append((cx,cy))
               for dx, dy in neigh:
                  nx, ny = cx + dx, cy + dy
                  if 0 <= nx < cols and 0 <= ny < rows and not visited[nx][ny]:
                     if is_water(nx, ny):
                        visited[nx][ny] = True
                        q.append((nx, ny))
                     else:
                        visited[nx][ny] = True  # mark non-water so we skip later

            # If component too small, convert to land
            if len(comp) < min_size:
               for cx, cy in comp:
                  tile = self.map_data[cx][cy]
                  # Convert to land
                  tile.set_grass(self._grass(cx, cy), "grassland")
   # noise
   def _elev(self, x, y):
      # Low-frequency base gives large water bodies; high-frequency detail adds natural edges.
      nx = x / self.cols * 3.5 + self._ex
      ny = y / self.rows * 3.5 + self._ey
      return (pnoise2(nx, ny, octaves=6, persistence=0.5, lacunarity=2.1) + 1) / 2

   def _moist(self, x, y):
      nx = x / self.cols * 2.8 + self._mx
      ny = y / self.rows * 2.8 + self._my
      return (pnoise2(nx, ny, octaves=4, persistence=0.55, lacunarity=2.0) + 1) / 2

   # asset pickers
   def _grass(self, x, y):
      # Single grass type to avoid visual noise index 0 always exists due to fallback.
      return self.assets["grass"][0]

   def _sand(self, x, y):
      pool = self.assets["sand"]
      return pool[(x * 2654435761 ^ y * 2246822519) % len(pool)]

   def _tree(self, biom):
      pool = self.assets["trees"].get(biom, self.assets["trees"]["oak"])
      return random.choice(pool)

   def _rock(self):
      return random.choice(self.assets["rocks"])

   # generation
   def generate_map(self):
      for x in range(self.cols):
         for y in range(self.rows):
            tile = self.map_data[x][y]
            elev = self._elev(x, y)
            mois = self._moist(x, y)

            if elev < _WATER_T:
               tile.set_water(random.choice(self.assets["water_deep"]), "deep")

            elif elev < _SAND_T:
               tile.set_sand(self._sand(x, y))

            elif elev > _HIGH_T:
               tile.set_grass(self._grass(x, y), "highland")

            elif mois > _OAK_T:
               tile.set_grass(self._grass(x, y), "oak_forest")
               if random.random() < 0.65:
                  tile.place_tree(self._tree("oak"))

            elif mois < _DARKPINE_T:
               tile.set_grass(self._grass(x, y), "darkpine_forest")
               if random.random() < 0.70:
                  tile.place_tree(self._tree("darkpine"))

            else:
               tile.set_grass(self._grass(x, y), "grassland")

      # Clean the random water tiles noise
      self._prune_small_lakes(min_size=6, connectivity=4)

      self._apply_water_depth()

      self._place_mountains()

      self._place_rock_clusters()

   def _apply_water_depth(self): # BFS algorithm for applying water depth
      dist = [[999] * self.rows for _ in range(self.cols)]
      q = deque()

      for x in range(self.cols):
         for y in range(self.rows):
            if self.map_data[x][y].biom != "lake":
               dist[x][y] = 0
               q.append((x, y))

      while q:
         cx, cy = q.popleft()
         d = dist[cx][cy]
         for dx, dy in ((-1,0),(1,0),(0,-1),(0,1)):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < self.cols and 0 <= ny < self.rows and dist[nx][ny] == 999:
               dist[nx][ny] = d + 1
               q.append((nx, ny))

      for x in range(self.cols):
         for y in range(self.rows):
            tile = self.map_data[x][y]
            if tile.biom != "lake":
               continue
            d = dist[x][y]
            if d <= _COAST_D:
               tile.set_water(random.choice(self.assets["water_coast"]), "coast")
            elif d <= _SHALLOW_D:
               tile.set_water(random.choice(self.assets["water_shallow"]), "shallow")

   def _place_mountains(self):
      visited = set()

      for sx in range(self.cols):
         for sy in range(self.rows):
            if self.map_data[sx][sy].biom != "highland" or (sx, sy) in visited:
               continue

            # Flood-fill this highland blob
            blob = []
            stack = [(sx, sy)]
            while stack:
               cx, cy = stack.pop()
               if (cx, cy) in visited:
                  continue
               if not (0 <= cx < self.cols and 0 <= cy < self.rows):
                  continue
               if self.map_data[cx][cy].biom != "highland":
                  continue
               visited.add((cx, cy))
               blob.append((cx, cy))
               stack += [(cx-1,cy),(cx+1,cy),(cx,cy-1),(cx,cy+1)]

            if len(blob) < 4:
               for bx, by in blob:
                  self.map_data[bx][by].set_grass(self._grass(bx, by), "grassland")
               continue

            # Centroid as peak
            cx = int(sum(p[0] for p in blob) / len(blob))
            cy = int(sum(p[1] for p in blob) / len(blob))
            cx = max(0, min(self.cols - 1, cx))
            cy = max(0, min(self.rows - 1, cy))

            peak_radius = max(1, int(math.sqrt(len(blob)) * 0.4))

            for bx, by in blob:
               tile = self.map_data[bx][by]
               tile.set_grass(self._grass(bx, by), "mountain")
               dist = math.hypot(bx - cx, by - cy)
               if dist <= 1.0:
                  tile.place_mountain_peak(random.choice(self.assets["mountain_peak"]))
               elif dist <= peak_radius:
                  tile.place_mountain_rock(random.choice(self.assets["mountain_rock"]))
               else:
                  tile.place_mountain_rock(random.choice(self.assets["mountain_rock"]))

   def _place_rock_clusters(self):
      # Scatters small rock clusters (3-7 tiles) across walkable non-forest land.
      # Rocks can bleed into forest edges for natural variety.
      cluster_count = (self.cols * self.rows) // 400

      for _ in range(cluster_count):
         ox = random.randint(0, self.cols - 1)
         oy = random.randint(0, self.rows - 1)
         tile = self.map_data[ox][oy]

         if tile.biom not in ("grassland", "oak_forest", "darkpine_forest"):
            continue

         cluster_size = random.randint(3, 7)
         cx, cy = ox, oy

         for _ in range(cluster_size):
            cx = max(0, min(self.cols - 1, cx + random.randint(-1, 1)))
            cy = max(0, min(self.rows - 1, cy + random.randint(-1, 1)))
            t = self.map_data[cx][cy]
            if t.walkable and t.obstacle in (None, "tree"):
               if t.obstacle == "tree":
                  t.remove_tree()
               t.place_rock(self._rock())

   # drawing
   def draw(self, screen):
      world = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
      for col in self.map_data:
         for tile in col:
               tile.draw(world)

      zw = int(self.width  * self.zoom_factor)
      zh = int(self.height * self.zoom_factor)
      screen.blit(pygame.transform.scale(world, (zw, zh)),
                  (-self.camera_offset.x, -self.camera_offset.y))

   def draw_grid(self, surface):
      g = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
      for x in range(0, surface.get_width(), self.tile_size):
         pygame.draw.line(g, (0,0,0,50), (x,0), (x, surface.get_height()))
      for y in range(0, surface.get_height(), self.tile_size):
         pygame.draw.line(g, (0,0,0,50), (0,y), (surface.get_width(), y))
      surface.blit(g, (0,0))

   # camera control
   def zoom_at(self, mouse_pos, direction, vw, vh):
      old = self.zoom_factor
      new = max(self.min_zoom, min(self.max_zoom, old + 0.3 * direction))
      if new == old:
         return
      mx, my = mouse_pos
      before = pygame.Vector2(mx, my) + self.camera_offset
      self.zoom_factor = new
      self.camera_offset = before * (new / old) - pygame.Vector2(mx, my)
      self.clamp_camera(vw, vh)

   def clamp_camera(self, sw, sh):
      self.camera_offset.x = max(0, min(self.camera_offset.x, self.width  * self.zoom_factor - sw))
      self.camera_offset.y = max(0, min(self.camera_offset.y, self.height * self.zoom_factor - sh))

   # tile access
   def screen_to_tile(self, mouse_pos):
      mx, my = mouse_pos
      tx = int((mx + self.camera_offset.x) / self.zoom_factor // self.tile_size)
      ty = int((my + self.camera_offset.y) / self.zoom_factor // self.tile_size)
      return (tx, ty) if (0 <= tx < self.cols and 0 <= ty < self.rows) else None

   def get_tile(self, mouse_pos):
      coords = self.screen_to_tile(mouse_pos)
      if coords:
         x, y = coords
         return self.map_data[x][y].to_dict()
      return None

   def get_tile_at(self, x, y):
      if 0 <= x < self.cols and 0 <= y < self.rows:
         return self.map_data[x][y]
      return None

   def is_walkable(self, x, y):
      t = self.get_tile_at(x, y)
      return t.walkable if t else False

   def tile_to_pixel(self, pos):
      return pos[0] * self.tile_size, pos[1] * self.tile_size

   def cut_tree(self, x, y):
      t = self.get_tile_at(x, y)
      if t and t.obstacle == "tree":
         t.remove_tree()
         return True
      return False

   def plant_tree(self, x, y):
      t = self.get_tile_at(x, y)
      if t and t.walkable and t.obstacle is None:
         t.place_tree(self._tree(t.biom))
         return True
      return False

   def add_rock(self, x, y):
      t = self.get_tile_at(x, y)
      if t and t.obstacle is None:
         t.place_rock(self._rock())
         return True
      return False

   def remove_rock(self, x, y):
      t = self.get_tile_at(x, y)
      if t and t.obstacle == "rock":
         t.remove_rock()
         return True
      return False

   # save/load
   def save_map(self, path="saved_map.json"):
      data = {
         "seeds": [self._ex, self._ey, self._mx, self._my],
         "tiles": [[t.to_dict() for t in col] for col in self.map_data],
      }
      with open(path, "w") as f:
         json.dump(data, f)

   def load_map(self, path="saved_map.json"):
      with open(path) as f:
         data = json.load(f)
      self._ex, self._ey, self._mx, self._my = data["seeds"]
      for col in data["tiles"]:
         for td in col:
            x, y = td["x"], td["y"]
            self.map_data[x][y] = Tile.from_dict(td, self.tile_size)
      self._reapply_surfaces()

   def _reapply_surfaces(self):
      # After load, tile state is restored but surfaces are gone – re-attach them here.
      for x in range(self.cols):
         for y in range(self.rows):
            t = self.map_data[x][y]
            obs = t.obstacle

            if t.biom == "lake":
               key = "water_coast" if "coast" in (obs or "") \
                     else "water_shallow" if "shallow" in (obs or "") \
                     else "water_deep"
               t.bg_surface = random.choice(self.assets[key])
            elif t.biom == "shore":
               t.bg_surface = self._sand(x, y)
            else:
               t.bg_surface = self._grass(x, y)
               if obs == "tree":
                  t.place_tree(self._tree(t.biom))
               elif obs == "rock":
                  t.place_rock(self._rock())
               elif obs == "mountain_peak":
                  t.place_mountain_peak(random.choice(self.assets["mountain_peak"]))
               elif obs == "mountain_rock":
                  t.place_mountain_rock(random.choice(self.assets["mountain_rock"]))

   # debugging
   def paint_explored_tiles(self, screen, camera_offset, zoom):
      for x in range(self.cols):
         for y in range(self.rows):
            if not self.map_data[x][y].explored:
               continue
            wx = x * self.tile_size + self.tile_size // 2
            wy = y * self.tile_size + self.tile_size // 2
            sx = int(wx * zoom - camera_offset[0])
            sy = int(wy * zoom - camera_offset[1])
            pygame.draw.circle(screen, (255, 0, 0), (sx, sy), max(1, int(3 * zoom)))

   def debug_draw_obstacles(self, screen):
      for x in range(self.cols):
         for y in range(self.rows):
            t = self.map_data[x][y]
            if t.obstacle:
               cx = int((x * self.tile_size + self.tile_size // 2) * self.zoom_factor - self.camera_offset.x)
               cy = int((y * self.tile_size + self.tile_size // 2) * self.zoom_factor - self.camera_offset.y)
               pygame.draw.circle(screen, (255, 0, 0), (cx, cy), 3)