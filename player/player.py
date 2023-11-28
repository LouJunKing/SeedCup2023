import json
import socket
from base import *
from req import *
from resp import *
from config import config
import logging
import numpy as np

from threading import Thread
from itertools import cycle
from time import sleep
from logger import logger

import sys


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
            return False
        return True


class player(object):

    def __init__(self, client):
        self.client = client
        self.action_map = \
            {(-1, 0): [ActionType.SILENT, ActionType.MOVE_UP],
             (1, 0): [ActionType.SILENT, ActionType.MOVE_DOWN],
             (0, -1): [ActionType.SILENT, ActionType.MOVE_LEFT],
             (0, 1): [ActionType.SILENT, ActionType.MOVE_RIGHT],
             (0, 0): [ActionType.SILENT, ActionType.SILENT],
             (-2, 0): [ActionType.MOVE_UP, ActionType.MOVE_UP],
             (2, 0): [ActionType.MOVE_DOWN, ActionType.MOVE_DOWN],
             (0, -2): [ActionType.MOVE_LEFT, ActionType.MOVE_LEFT],
             (0, 2): [ActionType.MOVE_RIGHT, ActionType.MOVE_RIGHT],
             (-1, -1, 0): [ActionType.MOVE_UP, ActionType.MOVE_LEFT],
             (-1, -1, 1): [ActionType.MOVE_LEFT, ActionType.MOVE_UP],
             (-1, 1, 0): [ActionType.MOVE_UP, ActionType.MOVE_RIGHT],
             (-1, 1, 1): [ActionType.MOVE_RIGHT, ActionType.MOVE_UP],
             (1, -1, 0): [ActionType.MOVE_DOWN, ActionType.MOVE_LEFT],
             (1, -1, 1): [ActionType.MOVE_LEFT, ActionType.MOVE_DOWN],
             (1, 1, 0): [ActionType.MOVE_DOWN, ActionType.MOVE_RIGHT],
             (1, 1, 1): [ActionType.MOVE_RIGHT, ActionType.MOVE_DOWN],
             (9): [ActionType.PLACED]}

    def start(self):
        self.client.connect()
        InitRequest = PacketReq(PacketType.InitReq, InitReq("89TxLwEAqklNCB23nVN+kA=="))
        # InitRequest = req.PacketReq(req.PacketType.InitReq, req.InitReq(self.client.config.get("player_name")))
        self.client.send(InitRequest)
        info = self.client.recv()
        self.player_id = info.data.player_id

        while True:
            action = self.decision(info)
            actions = []
            for action in action:
                actions.append(ActionReq(playerID=self.player_id,
                                         actionType=action))
            action_request = PacketReq(type=PacketType.ActionReq, data=actions)
            self.client.send(action_request)
            info = self.client.recv()
            if info.type == PacketType.GameOver:
                break


    def bomb_value(self, map, x, y):
        value = 0
        for i in range(1, self.player_info["bomb_range"] + 1):
            if x - i >= 0 and map[x - i, y] == 2:
                value += 10
                break
            elif x - i >= 0 and 7 >= map[x - i, y] >= 3:
                value -= 50
                break
            elif x - i >= 0 and map[x - i, y] == 1:
                break
        for i in range(1, self.player_info["bomb_range"] + 1):
            if x + i <= 14 and map[x + i, y] == 2:
                value += 10
                break
            elif x + i <= 14 and 7 >= map[x + i, y] >= 3:
                value -= 50
                break
            elif x + i <= 14 and map[x + i, y] == 1:
                break
        for i in range(1, self.player_info["bomb_range"] + 1):
            if y - i >= 0 and map[x, y - i] == 2:
                value += 10
                break
            elif y - i >= 0 and 7 >= map[x, y - i] >= 3:
                value -= 50
                break
            elif y - i >= 0 and map[x, y - i] == 1:
                break
        for i in range(1, self.player_info["bomb_range"] + 1):
            if y + i <= 14 and map[x, y + i] == 2:
                value += 10
                break
            elif y + i <= 14 and 7 >= map[x, y + i] >= 3:
                value -= 50
                break
            elif y + i <= 14 and map[x, y + i] == 1:
                break
        return value

    def move_value(self, map, dis, bombs):
        value = []
        for pos in dis.keys():
            tvalue = 0
            if 3 <= map[pos] <= 7:
                tvalue += 10
            if self.bomb(pos[0], pos[1], bombs):
                tvalue -= 300
            tvalue -= dis[pos][0]*2
            tvalue += dis[pos][2]
            value.append((pos, tvalue))
        return value

    def bomb(self, x, y, bombs):
        for bomb in bombs:
            if bomb[0][0] == x and bomb[0][1] - bomb[1] <= y <= bomb[0][1] + bomb[1]:
                return True
            elif bomb[0][1] == y and bomb[0][0] - bomb[1] <= x <= bomb[0][0] + bomb[1]:
                return True
        return False
    
    def decision(self, info):
        map, self.player_info, bombs = self.map_encode(info.data.map)
        dis = self.search(map, self.player_info["x"], self.player_info["y"], bombs)
        value = self.move_value(map, dis, bombs)
        pos, best_value = max(value, key=lambda x: x[1])
        if pos[0] == self.player_info["x"] and pos[1] == self.player_info["y"] and best_value >= 0:
            action = self.action_map[(9)]
        else:
            action = dis[pos][1]
        return action

    def search(self, map, x, y, bombs):
        ground = np.full((15, 15), True)
        visit = []
        dis = {(x, y): [0, self.action_map[(0, 0)], self.bomb_value(map, x, y)]}
        i, j = x, y
        ground[i, j] = False
        # 初始化， 决定下一步移动
        for dx, dy in ((-1, 0), (1, 0), (0, 1), (0, -1)):
            if 0 > i + dx or i + dx > 14 or 0 > j + dy or j + dy > 14:
                continue
            elif map[i + dx, j + dy] in (1, 2) or map[i + dx, j + dy] >= 8:
                continue
            else:
                if ground[i + dx, j + dy]:
                    visit.append((i + dx, j + dy))
                    dis[(i + dx, j + dy)] = [dis[i, j][0] + 1, self.action_map[(dx, dy)]]
                    ground[i + dx, j + dy] = False
                elif dis[(i + dx, j + dy)][0] > dis[i, j][0] + 1:
                    dis[(i + dx, j + dy)][0] = dis[i, j][0] + 1
                    dis[(i + dx, j + dy)][1] = self.action_map[(dx, dy)]
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            if 0 > i + dx or i + dx > 14 or 0 > j + dy or j + dy > 14:
                continue
            elif map[i + dx, j + dy] in (1, 2) or map[i + dx // 2, j + dy // 2] in (1, 2) or map[i + dx, j + dy] >= 8 or map[i + dx // 2, j + dy // 2] >= 8:
                continue
            else:
                if ground[i + dx, j + dy]:
                    visit.append((i + dx, j + dy))
                    dis[(i + dx, j + dy)] = [dis[i, j][0] + 1, self.action_map[(dx, dy)]]
                    ground[i + dx, j + dy] = False
                elif dis[(i + dx, j + dy)][0] > dis[i, j][0] + 1:
                    dis[(i + dx, j + dy)][0] = dis[i, j][0] + 1
                    dis[(i + dx, j + dy)][1] = self.action_map[(dx, dy)]
        for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            if 0 > i + dx or i + dx > 14 or 0 > j + dy or j + dy > 14:
                continue
            elif map[i + dx, j + dy] in (1, 2) or map[i + dx, j + dy] >= 8:
                continue
            elif (map[i + dx, j] in (1, 2) or map[i + dx, j] >= 8) and (map[i, j + dy] in (1, 2) or map[i, j + dy] >= 8):
                continue
            elif map[i + dx, j] not in (1, 2) and map[i + dx, j] < 8:
                if ground[i + dx, j + dy]:
                    visit.append((i + dx, j + dy))
                    dis[(i + dx, j + dy)] = [dis[i, j][0] + 1, self.action_map[(dx, dy, 0)]]
                    ground[i + dx, j + dy] = False
                elif dis[(i + dx, j + dy)][0] > dis[i, j][0] + 1:
                    dis[(i + dx, j + dy)][0] = dis[i, j][0] + 1
                    dis[(i + dx, j + dy)][1] = self.action_map[(dx, dy, 0)]
            else:
                if ground[i + dx, j + dy]:
                    visit.append((i + dx, j + dy))
                    dis[(i + dx, j + dy)] = [dis[i, j][0] + 1, self.action_map[(dx, dy, 1)]]
                    ground[i + dx, j + dy] = False
                elif dis[(i + dx, j + dy)][0] > dis[i, j][0] + 1:
                    dis[(i + dx, j + dy)][0] = dis[i, j][0] + 1
                    dis[(i + dx, j + dy)][1] = self.action_map[(dx, dy, 1)]
        # 遍历剩余连通区域， 广度优先
        while visit != []:
            i, j = visit.pop(0)
            dis[(i, j)].append(self.bomb_value(map, i, j))
            if self.bomb(i, j, bombs):
                dis[(i, j)][0] += 10
            for dx, dy in ((-1, 0), (1, 0), (0, 1), (0, -1)):
                if 0 > i + dx or i + dx > 14 or 0 > j + dy or j + dy > 14:
                    continue
                elif map[i + dx, j + dy] in (1, 2):
                    continue
                else:
                    if ground[i + dx, j + dy]:
                        visit.append((i + dx, j + dy))
                        dis[(i + dx, j + dy)] = [dis[(i, j)][0] + 1, dis[(i, j)][1]]
                        ground[i + dx, j + dy] = False
                    elif dis[(i + dx, j + dy)][0] > dis[(i, j)][0] + 1:
                        dis[(i + dx, j + dy)][0] = dis[(i, j)][0] + 1
                        dis[(i + dx, j + dy)][1] = dis[(i, j)][1]
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                if 0 > i + dx or i + dx > 14 or 0 > j + dy or j + dy > 14:
                    continue
                elif map[i + dx, j + dy] in (1, 2) or map[i + dx // 2, j + dy // 2] in (1, 2):
                    continue
                else:
                    if ground[i + dx, j + dy]:
                        visit.append((i + dx, j + dy))
                        dis[(i + dx, j + dy)] = [dis[(i, j)][0] + 1, dis[(i, j)][1]]
                        ground[i + dx, j + dy] = False
                    elif dis[(i + dx, j + dy)][0] >= dis[(i, j)][0] + 1:
                        dis[(i + dx, j + dy)][0] = dis[(i, j)][0] + 1
                        dis[(i + dx, j + dy)][1] = dis[(i, j)][1]
            for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                if 0 > i + dx or i + dx > 14 or 0 > j + dy or j + dy > 14:
                    continue
                elif map[i + dx, j + dy] in (1, 2) or (map[i + dx, j] in (1, 2) and map[i, j + dy] in (1, 2)):
                    continue
                else:
                    if ground[i + dx, j + dy]:
                        visit.append((i + dx, j + dy))
                        dis[(i + dx, j + dy)] = [dis[(i, j)][0] + 1, dis[(i, j)][1]]
                        ground[i + dx, j + dy] = False
                    elif dis[(i + dx, j + dy)][0] >= dis[(i, j)][0] + 1:
                        dis[(i + dx, j + dy)][0] = dis[(i, j)][0] + 1
                        dis[(i + dx, j + dy)][1] = dis[(i, j)][1]
        return dis

    def map_encode(self, map_resp):
        ground = np.zeros((15, 15), dtype=int)
        player_info = np.zeros(9)
        bombs = []
        for block in map_resp:
            x = block.x
            y = block.y
            for obj in block.objs:
                if obj.type == ObjType.Null:
                    continue
                elif obj.type == ObjType.Player:
                    if obj.property.player_id == self.player_id:
                        player_info = {"x": x, "y": y, "hp": obj.property.hp, "shield_time": obj.property.shield_time,
                                       "invincible_time": obj.property.invincible_time,
                                       "bomb_range": obj.property.bomb_range,
                                       "bomb_max_num": obj.property.bomb_max_num,
                                       "bomb_now_num": obj.property.bomb_now_num,
                                       "speed": obj.property.speed, "score": obj.property.score}
                elif obj.type == ObjType.Bomb:
                    ground[x, y] = 8 + obj.property.bomb_range
                    bombs.append(((x, y), obj.property.bomb_range))
                elif obj.type == ObjType.Block:
                    if obj.property.removable is True:
                        ground[x, y] = 2
                    else:
                        ground[x, y] = 1
                elif obj.type == ObjType.Item:
                    ground[x, y] = obj.property.item_type + 2

        return ground, player_info, bombs

if __name__ == "__main__":
    player = player(Client())
    player.start()
    