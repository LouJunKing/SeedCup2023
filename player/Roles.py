import numpy as np

DISTANCE = [(0, 1), (0, -1), (1, 0), (-1, 0)]

class Role:
  def __init__(self, FSM):
    self.FSM = FSM
  
  def start(self):
    pass

  def update(self):
    pass

  def end(self):
    pass

  def BFS(self, i, j):
    """
    BFS+dp
    search for reachable location and the path
    return a dict: {(x, y): [distance, path]}
    """
    global DISTANCE
    reachable = {(i, j):[0, []]} # (x, y): [distance, path]
    visit = [(i, j)]
    ground = np.zeros((self.FSM.map_size, self.FSM.map_size))
    while(len(visit) != 0):
      x, y = visit.pop(0)
      ground[x, y] = 1
      for dx, dy in DISTANCE:
        _x, _y = x + dx, y + dy
        if _x < 0 or _x >= self.FSM.map_size or _y < 0 or _y >= self.FSM.map_size or (self.FSM.Map[_x, _y] > 0 and self.FSM.Map[_x, _y] not in (0, 4, 5, 6, 7, 8, 9, 10)):
          continue
        else:
          if ground[_x, _y] == 0:
            ground[_x, _y] = reachable[(x, y)][0] + 1
            reachable[(_x, _y)] = [reachable[(x, y)][0] + 1, reachable[(x, y)][1] + [(dx, dy)]]
            visit.append((_x, _y))
          elif reachable[(_x, _y)][0] > reachable[(x, y)][0] + 1:
            reachable[(_x, _y)] = [reachable[(x, y)][0] + 1, reachable[(x, y)][1] + [(dx, dy)]]
    return self.safe_path(reachable)
  
  def safe_path(self, reachable):
    """
    return the safe reachable path
    """
    new_reachable = {}
    round_conter = 1
    for (x, y) in reachable.keys():
      dis = reachable[(x, y)][0]
      path = reachable[(x, y)][1]
      new_path = path
      tx, ty = self.FSM.player_info["x"], self.FSM.player_info["y"]
      path_counter = 0
      round_conter = 1
      danger = self.FSM.player_info["speed"]
      safe = danger
      i = 0
      flag = True
      while (tx, ty) != (x, y):
        move = new_path[i]
        path_counter += 1
        tx += move[0]
        ty += move[1]
        if self.FSM.bomb_region[tx, ty, round_conter] == 0:
          safe = path_counter
        else:
          danger -= 1
        i += 1
        if danger <= 0:
          flag = False
          break
        if path_counter == self.FSM.player_info["speed"]:
          path_counter = 0
          round_conter += 1
          danger = self.FSM.player_info["speed"]
          for _ in range(danger - safe):
            tx -= new_path[i - 1][0]
            ty -= new_path[i - 1][1]
            new_path.insert(i - danger + safe, (0, 0))
          dis += danger-safe
          safe = danger
        if round_conter >= 7:
          break
      if round_conter < 7:
        if self.FSM.bomb_region[x, y, round_conter] != 0:
          flag = False
      if flag:
        new_reachable[(x, y)] = [dis, new_path, self.Value(x, y, [dis, new_path])]
    return new_reachable
  
  def Value(self, x, y, walk):
    pass


class Miner(Role):
  def __init__(self, FSM):
    super().__init__(FSM)

  def update(self):
    """
    update the map and player info
    """
    print("Mine")
    reachable = self.BFS(self.FSM.player_info["x"], self.FSM.player_info["y"])
    print(reachable)
    if len(reachable.keys()) == 0:
      return [(0, 0)]
    dest, dest_info = max(reachable.items(), key=lambda x: x[1][2])
    if dest == (self.FSM.player_info["x"], self.FSM.player_info["y"]):
      if self.bombable(dest[0], dest[1], reachable):
        self.FSM.change_player(Escaper(self.FSM))
        return [(5)]
      else:
        return [(0, 0)]
    else:
      path = dest_info[1]
      return path[:min(len(path), self.FSM.player_info["speed"])]

  def Value(self, x, y, walk):
    """
    calculate the value of a location
    """
    value = 0
    if self.FSM.Map[x, y] == 11:
      value -= 500
    for dis in range(1, self.FSM.player_info["bomb_range"] + 1):
      if x + dis >= self.FSM.map_size:
        break
      if self.FSM.Map[x + dis, y] == 1:
        break
      if self.FSM.Map[x + dis, y] == 11:
        break
      if self.FSM.Map[x + dis, y] == 2:
        value += 100
        break
      if 11 > self.FSM.Map[x + dis, y] > 3:
        value -= 400
        break
    for dis in range(1, self.FSM.player_info["bomb_range"] + 1):
      if y + dis >= self.FSM.map_size:
        break
      if self.FSM.Map[x, y + dis] == 1:
        break
      if self.FSM.Map[x, y + dis] == 11:
        break
      if self.FSM.Map[x, y + dis] == 2:
        value += 100
        break
      if 11 > self.FSM.Map[x, y + dis] > 3:
        value -= 400
        break
    for dis in range(1, self.FSM.player_info["bomb_range"] + 1):
      if x - dis < 0:
        break
      if self.FSM.Map[x - dis, y] == 1:
        break
      if self.FSM.Map[x - dis, y] == 11:
        break
      if self.FSM.Map[x - dis, y] == 2:
        value += 100
        break
      if 11 > self.FSM.Map[x - dis, y] > 3:
        value -= 400
        break
    for dis in range(1, self.FSM.player_info["bomb_range"] + 1):
      if y + dis < 0:
        break
      if self.FSM.Map[x, y - dis] == 1:
        break
      if self.FSM.Map[x, y - dis] == 11:
        break
      if self.FSM.Map[x, y - dis] == 2:
        value += 100
        break
      if 11 > self.FSM.Map[x, y - dis] > 3:
        value -= 400
        break
    value -= walk[0]//self.FSM.player_info["speed"]
    return value
  
  def bombable(self, x, y, reachable):
    """
    check if the place is safe to place bomb
    """
    self.FSM.Map[x, y] = 10
    self.FSM.bomb_list[-1] = [x, y, self.FSM.player_info["bomb_range"], 0, 5]
    self.FSM.gen_bomb_region()
    available = self.BFS(x, y).keys()
    for (tx, ty) in available:
      flag = True
      for i in range(7):
        if self.FSM.bomb_region[tx, ty, i] != 0:
          flag = False
      if flag:
        return flag
    return False
      
  

class Escaper(Role):
  def __init__(self, FSM):
    super().__init__(FSM)

  def update(self):
    print("Escape")
    reachable = self.BFS(self.FSM.player_info["x"], self.FSM.player_info["y"])
    if len(reachable.keys()) == 0:
      return [(0, 0)]
    dest, dest_info = max(reachable.items(), key=lambda x: x[1][2])
    print(reachable)
    if dest == (self.FSM.player_info["x"], self.FSM.player_info["y"]):
      self.FSM.change_player(reachable = reachable)
      return self.FSM.player.update()
    else:
      path = dest_info[1]
      return path[:min(len(path), self.FSM.player_info["speed"])]

  def Value(self, x, y, walk):
    value = 0
    flag = True
    for i in range(7):
      if self.FSM.bomb_region[x, y, i] != 0:
        flag = False
    if flag:
      value += 100
    return value - 2*walk[0]//self.FSM.player_info["speed"]
  

class Walker(Role):
  def __init__(self, FSM):
    super().__init__(FSM)

  def update(self):
    print("Walk")
    reachable = self.BFS(self.FSM.player_info["x"], self.FSM.player_info["y"])
    print(reachable)
    if len(reachable.keys()) == 0:
      return [(0, 0)]
    dest, dest_info = max(reachable.items(), key=lambda x: x[1][2])
    if dest == (self.FSM.player_info["x"], self.FSM.player_info["y"]):
      self.FSM.Map[dest[0], dest[1]] = 0
      self.FSM.change_player(reachable = reachable)
      return self.FSM.player.update()
    else:
      path = dest_info[1]
      return path[:min(len(path), self.FSM.player_info["speed"])]

  def Value(self, x, y, walk):
    value = 0
    if 4 <= self.FSM.Map[x, y] <= 10:
      value += 100
    value -= walk[0]
    return value
    
class Hunter(Role):
  pass

