from heapq import heappush, heappop

class AStar:
   def __init__(self, game_map):
      self.map = game_map

   # Heuristics for finding the shortest path from A to B
   def heuristic(self, a, b):
      return abs(a[0] - b[0]) + abs(a[1] - b[1])

   # the A* algorithm
   def find_path(self, start, end):
      if start == end:
         return []

      open_set = []
      came_from = {}

      g_score = {start: 0}
      f_score = {start: self.heuristic(start, end)}

      heappush(open_set, (f_score[start], start))

      while open_set:
         _, current = heappop(open_set)

         if current == end:
               return self.reconstruct_path(came_from, current)

         for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
               neighbor = (current[0] + dx, current[1] + dy)

               if not self.map.is_walkable(*neighbor):
                  continue

               tentative_g = g_score[current] + 1

               if neighbor not in g_score or tentative_g < g_score[neighbor]:
                  came_from[neighbor] = current
                  g_score[neighbor] = tentative_g
                  f_score[neighbor] = tentative_g + self.heuristic(neighbor, end)

                  heappush(open_set, (f_score[neighbor], neighbor))

      return []

   # Path rebuild
   def reconstruct_path(self, came_from, current):
      path = [current]

      while current in came_from:
         current = came_from[current]
         path.append(current)

      return path[::-1]