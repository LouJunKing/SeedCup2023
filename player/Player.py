import numpy as np
import sys
import json
import socket

from config import config
from base import *
from Roles import *
from req import *
from resp import *
from logger import logger

DISTANCE = [(0, 0), (0, -1), (0, 1), (-1, 0), (1, 0)]
class Client(object):
    """Client obj that send/recv packet.
    """

    def __init__(self) -> None:
        self.config = config
        self.host = self.config.get("host")
        self.port = self.config.get("port")
        assert self.host and self.port, "host and port must be provided"
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._connected = False

    def connect(self):
        if self.socket.connect_ex((self.host, self.port)) == 0:
            logger.info(f"connect to {self.host}:{self.port}")
            self._connected = True
        else:
            logger.error(f"can not connect to {self.host}:{self.port}")
            exit(-1)
        return

    def send(self, req: PacketReq):
        msg = json.dumps(req, cls=JsonEncoder).encode("utf-8")
        length = len(msg)
        self.socket.sendall(length.to_bytes(8, sys.byteorder) + msg)
        # uncomment this will show req packet
        # logger.info(f"send PacketReq, content: {msg}")
        return

    def recv(self):
        length = int.from_bytes(self.socket.recv(8), sys.byteorder)
        result = b""
        while resp := self.socket.recv(length):
            result += resp
            length -= len(resp)
            if length <= 0:
                break

        # uncomment this will show resp packet
        # logger.info(f"recv PacketResp, content: {result}")
        packet = PacketResp().from_json(result)
        return packet

    def __enter__(self):
        return self

    def close(self):
        logger.info("closing socket")
        self.socket.close()
        logger.info("socket closed successfully")
        self._connected = False

    @property
    def connected(self):
        return self._connected

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        if traceback:
            # print(traceback)
            return False
        return True


ACTION_LIST = {
  (0, 0): ActionType.SILENT,
  (0, 1): ActionType.MOVE_RIGHT,
  (0, -1): ActionType.MOVE_LEFT,
  (1, 0): ActionType.MOVE_DOWN,
  (-1, 0): ActionType.MOVE_UP,
  (5): ActionType.PLACED
}


class Brain:
  def __init__(self, client):
    self.client = client
    self.Map = None
    self.player_info = None

  def GameStart(self, player_name):
    self.client.connect()
    InitRequest = PacketReq(PacketType.InitReq, InitReq(player_name))
    self.client.send(InitRequest)
    info = self.client.recv()
    self.FSM = FSM(config.get("map_size"), info)
    
    return info

  def GameUpdate(self, info) -> None:
    print(f"round:{info.data.round}")
    actions = self.FSM.update(info.data.map)
    action_list = []
    for action in actions:
      action_list.append(ActionReq(playerID=self.FSM.player_id, actionType=ACTION_LIST[action]))
    action_request = PacketReq(type=PacketType.ActionReq, data=action_list)
    self.client.send(action_request)
    info = self.client.recv()
    return info

  def GameOver(self, info) -> None:
    pass
    
  
class FSM:
  def __init__(self, map_size, info) -> None:
    self.player = Miner(self)
    self.player.start()
    self.map_size = map_size
    self.player_id = info.data.player_id
    self.Map = None
    self.bomb_region = np.zeros((self.map_size, self.map_size, 6))
    self.bomb_list = {} # {bomb_id: [x, y, range, status, time]}
    self.player_info = None
    self.condition = {"item": False, "oppent": {}}

  def change_player(self, player: Role = None, reachable = None) -> None:
    self.player.end()
    if player is not None:
      self.player = player
    else:
       self.player = self.choose_player(reachable)
    self.player.start()

  def choose_player(self, reachable) -> Role:
    for (x, y) in reachable.keys():
      if 4 <= self.Map[x, y] <= 10:
        return Walker(self)
    return Miner(self)

  def update(self, map_resp):
    self.Map_encode(map_resp)
    self.gen_bomb_region()
    print(self.bomb_list)
    actions = self.player.update()
    print(actions)
    return actions
  
  def Map_encode(self, map_resp) -> None:
    """
    encode the map
    blank: 0
    walll: 1
    block: 2
    opponent: -opponent_id
    item: 4-10
    bomb: 11
    """
    ground = np.zeros((self.map_size, self.map_size), dtype=int)
    player_info = None
    bomb_list = {}
    condition = {"item": False, "oppent": {}}
    for block in map_resp:
      x = block.x
      y = block.y
      for obj in block.objs:
        if obj.type == ObjType.Null:
          continue
        elif obj.type == ObjType.Player:
          if obj.property.player_id == self.player_id:
            player_info = {"x": x, "y": y, "hp": obj.property.hp, "shield_time": obj.property.shield_time,
                          "invincible_time": obj.property.invincible_time, "bomb_range": obj.property.bomb_range,
                          "bomb_max_num": obj.property.bomb_max_num, "bomb_now_num": obj.property.bomb_now_num,
                          "speed": obj.property.speed, "has_gloves": obj.property.has_gloves}
            score = obj.property.score
          else:
            ground[x, y] = -obj.property.player_id
            oppo_player_info = {"x": x, "y": y, "hp": obj.property.hp, "shield_time": obj.property.shield_time,
                          "invincible_time": obj.property.invincible_time, "bomb_range": obj.property.bomb_range,
                          "bomb_max_num": obj.property.bomb_max_num, "bomb_now_num": obj.property.bomb_now_num,
                          "speed": obj.property.speed, "has_gloves": obj.property.has_gloves}
            oppo_player_id = obj.property.player_id
            condition["oppent"][oppo_player_id] = oppo_player_info
        elif obj.type == ObjType.Bomb:
          if obj.property.bomb_id not in self.bomb_list.keys():
            bomb_list[obj.property.bomb_id] = [x, y, obj.property.bomb_range, obj.property.bomb_status, 6]
          else:
            bomb_list[obj.property.bomb_id] = [x, y, obj.property.bomb_range, obj.property.bomb_status, self.bomb_list[obj.property.bomb_id][4] - 1]
          ground[x, y] = 11
        elif obj.type == ObjType.Block:
          if obj.property.removable is True:
            ground[x, y] = max(2, ground[x, y])
          else:
            ground[x, y] = 1
        elif obj.type == ObjType.Item:
          ground[x, y] = obj.property.item_type + 3

    self.Map = ground
    self.player_info = player_info
    self.score = score
    self.bomb_list = bomb_list
    self.condition = condition
    return

  def gen_bomb_region(self):
    """
    generate the bomb region
    [x, y, round]
    """
    bomb_region = np.zeros((self.map_size, self.map_size, 7))
    global DISTANCE
    for bomb_id in self.bomb_list.keys():
      x, y, bomb_range, bomb_status, time = self.bomb_list[bomb_id]
      dx, dy = DISTANCE[bomb_status]
      for round in range(time):
        if 0 <= x+round*dx < self.map_size and 0 <= y+round*dy < self.map_size:
          bomb_region[x+round*dx, y+round*dy, round] = -bomb_id
    while True:
      flag = True
      for bomb_id in self.bomb_list.keys():
        x, y, bomb_range, bomb_status, time = self.bomb_list[bomb_id]
        dx, dy = DISTANCE[bomb_status]
        if time > 1:
          tx, ty = max(min(x + dx*time, self.map_size-1), 0), max(min(y + dy*time, self.map_size-1), 0)
          tx_1, ty_1 = max(min(x + dx*(time - 1), self.map_size-1), 0), max(min(y + dy*(time - 1), self.map_size-1), 0)
          for b_range in range(1, bomb_range+1):
            if tx + b_range < self.map_size: 
              if bomb_region[tx + b_range, ty, time] < 0:
                other_id = -bomb_region[tx + b_range, ty, time]
                if self.bomb_list[bomb_id][4] > self.bomb_list[other_id][4]:
                  self.bomb_list[bomb_id][4] = self.bomb_list[other_id][4]
                  flag = False
                elif self.bomb_list[bomb_id][4] < self.bomb_list[other_id][4]:
                  self.bomb_list[other_id][4] = self.bomb_list[bomb_id][4]
                  flag = False
              bomb_region[tx + b_range, ty, time] = 1
            if tx - b_range >= 0:
              if bomb_region[tx - b_range, ty, time] < 0:
                other_id = -bomb_region[tx - b_range, ty, time]
                if self.bomb_list[bomb_id][4] > self.bomb_list[other_id][4]:
                  self.bomb_list[bomb_id][4] = self.bomb_list[other_id][4]
                  flag = False
                elif self.bomb_list[bomb_id][4] < self.bomb_list[other_id][4]:
                  self.bomb_list[other_id][4] = self.bomb_list[bomb_id][4]
                  flag = False
              bomb_region[tx - b_range, ty, time] = 1
            if ty + b_range < self.map_size:
              if bomb_region[tx, ty + b_range, time] < 0:
                other_id = -bomb_region[tx, ty + b_range, time]
                if self.bomb_list[bomb_id][4] > self.bomb_list[other_id][4]:
                  self.bomb_list[bomb_id][4] = self.bomb_list[other_id][4]
                  flag = False
                elif self.bomb_list[bomb_id][4] < self.bomb_list[other_id][4]:
                  self.bomb_list[other_id][4] = self.bomb_list[bomb_id][4]
                  flag = False
              bomb_region[tx, ty + b_range, time] = 1
            if ty - b_range >= 0:
              if bomb_region[tx, ty - b_range, time] < 0:
                other_id = -bomb_region[tx, ty - b_range, time]
                if self.bomb_list[bomb_id][4] > self.bomb_list[other_id][4]:
                  self.bomb_list[bomb_id][4] = self.bomb_list[other_id][4]
                  flag = False
                elif self.bomb_list[bomb_id][4] < self.bomb_list[other_id][4]:
                  self.bomb_list[other_id][4] = self.bomb_list[bomb_id][4]
                  flag = False
              bomb_region[tx, ty - b_range, time] = 1
            if tx_1 + b_range < self.map_size: 
              if bomb_region[tx_1 + b_range, ty_1, (time - 1)] < 0:
                other_id = -bomb_region[tx_1 + b_range, ty_1, (time - 1)]
                if self.bomb_list[bomb_id][4] > self.bomb_list[other_id][4]:
                  self.bomb_list[bomb_id][4] = self.bomb_list[other_id][4]
                  flag = False
                elif self.bomb_list[bomb_id][4] < self.bomb_list[other_id][4]:
                  self.bomb_list[other_id][4] = self.bomb_list[bomb_id][4]
                  flag = False
              bomb_region[tx_1 + b_range, ty_1, (time - 1)] = 1
            if tx_1 - b_range >= 0:
              if bomb_region[tx_1 - b_range, ty_1, (time - 1)] < 0:
                other_id = -bomb_region[tx_1 - b_range, ty_1, (time - 1)]
                if self.bomb_list[bomb_id][4] > self.bomb_list[other_id][4]:
                  self.bomb_list[bomb_id][4] = self.bomb_list[other_id][4]
                  flag = False
                elif self.bomb_list[bomb_id][4] < self.bomb_list[other_id][4]:
                  self.bomb_list[other_id][4] = self.bomb_list[bomb_id][4]
                  flag = False
              bomb_region[tx_1 - b_range, ty_1, (time - 1)] = 1
            if ty_1 + b_range < self.map_size:
              if bomb_region[tx_1, ty_1 + b_range, (time - 1)] < 0:
                other_id = -bomb_region[tx_1, ty_1 + b_range, (time - 1)]
                if self.bomb_list[bomb_id][4] > self.bomb_list[other_id][4]:
                  self.bomb_list[bomb_id][4] = self.bomb_list[other_id][4]
                  flag = False
                elif self.bomb_list[bomb_id][4] < self.bomb_list[other_id][4]:
                  self.bomb_list[other_id][4] = self.bomb_list[bomb_id][4]
                  flag = False
              bomb_region[tx_1, ty_1 + b_range, (time - 1)] = 1
            if ty_1 - b_range >= 0:
              if bomb_region[tx_1, ty_1 - b_range, (time - 1)] < 0:
                other_id = -bomb_region[tx_1, ty_1 - b_range, (time - 1)]
                if self.bomb_list[bomb_id][4] > self.bomb_list[other_id][4]:
                  self.bomb_list[bomb_id][4] = self.bomb_list[other_id][4]
                  flag = False
                elif self.bomb_list[bomb_id][4] < self.bomb_list[other_id][4]:
                  self.bomb_list[other_id][4] = self.bomb_list[bomb_id][4]
                  flag = False
              bomb_region[tx_1, ty_1 - b_range, (time - 1)] = 1
        else:
          tx, ty = max(min(x + dx*time, self.map_size-1), 0), max(min(y + dy*time, self.map_size-1), 0)
          for b_range in range(1, bomb_range+1):
            if tx + b_range < self.map_size: 
              if bomb_region[tx + b_range, ty, time] < 0:
                other_id = -bomb_region[tx + b_range, ty, time]
                if self.bomb_list[bomb_id][4] > self.bomb_list[other_id][4]:
                  self.bomb_list[bomb_id][4] = self.bomb_list[other_id][4]
                  flag = False
                elif self.bomb_list[bomb_id][4] < self.bomb_list[other_id][4]:
                  self.bomb_list[other_id][4] = self.bomb_list[bomb_id][4]
                  flag = False
              bomb_region[tx + b_range, ty, time] = 1
            if tx - b_range >= 0:
              if bomb_region[tx - b_range, ty, time] < 0:
                other_id = -bomb_region[tx - b_range, ty, time]
                if self.bomb_list[bomb_id][4] > self.bomb_list[other_id][4]:
                  self.bomb_list[bomb_id][4] = self.bomb_list[other_id][4]
                  flag = False
                elif self.bomb_list[bomb_id][4] < self.bomb_list[other_id][4]:
                  self.bomb_list[other_id][4] = self.bomb_list[bomb_id][4]
                  flag = False
              bomb_region[tx - b_range, ty, time] = 1
            if ty + b_range < self.map_size:
              if bomb_region[tx, ty + b_range, time] < 0:
                other_id = -bomb_region[tx, ty + b_range, time]
                if self.bomb_list[bomb_id][4] > self.bomb_list[other_id][4]:
                  self.bomb_list[bomb_id][4] = self.bomb_list[other_id][4]
                  flag = False
                elif self.bomb_list[bomb_id][4] < self.bomb_list[other_id][4]:
                  self.bomb_list[other_id][4] = self.bomb_list[bomb_id][4]
                  flag = False
              bomb_region[tx, ty + b_range, time] = 1
            if ty - b_range >= 0:
              if bomb_region[tx, ty - b_range, time] < 0:
                other_id = -bomb_region[tx, ty - b_range, time]
                if self.bomb_list[bomb_id][4] > self.bomb_list[other_id][4]:
                  self.bomb_list[bomb_id][4] = self.bomb_list[other_id][4]
                  flag = False
                elif self.bomb_list[bomb_id][4] < self.bomb_list[other_id][4]:
                  self.bomb_list[other_id][4] = self.bomb_list[bomb_id][4]
                  flag = False
              bomb_region[tx, ty - b_range, time] = 1
      if flag:
        break    
    self.bomb_region = bomb_region
    return

if __name__ == "__main__":
  client = Client()
  brain = Brain(client)
  info = brain.GameStart("Lou_Jun")
  while True:
    info = brain.GameUpdate(info)
    if info.type == PacketType.GameOver:
      break
  brain.GameOver(info)