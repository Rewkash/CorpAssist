from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket


@dataclass(frozen=True)
class ChatSocketClient:
    user_id: int
    role: str
    websocket: WebSocket


class ChatSocketHub:
    def __init__(self) -> None:
        self._conversation_rooms: dict[int, set[ChatSocketClient]] = defaultdict(set)
        self._user_connections: dict[int, set[ChatSocketClient]] = defaultdict(set)

    def connect(self, conversation_id: int, client: ChatSocketClient) -> None:
        self._conversation_rooms[conversation_id].add(client)
        self._user_connections[client.user_id].add(client)

    def disconnect(self, conversation_id: int, client: ChatSocketClient) -> None:
        room = self._conversation_rooms.get(conversation_id)
        if room and client in room:
            room.remove(client)
            if not room:
                self._conversation_rooms.pop(conversation_id, None)
        user_sockets = self._user_connections.get(client.user_id)
        if user_sockets and client in user_sockets:
            user_sockets.remove(client)
            if not user_sockets:
                self._user_connections.pop(client.user_id, None)

    async def send_to_conversation(self, conversation_id: int, payload: dict[str, Any]) -> None:
        targets = list(self._conversation_rooms.get(conversation_id, set()))
        for client in targets:
            try:
                await client.websocket.send_json(payload)
            except Exception:
                self.disconnect(conversation_id, client)

    async def send_to_user(self, user_id: int, payload: dict[str, Any]) -> None:
        targets = list(self._user_connections.get(user_id, set()))
        for client in targets:
            try:
                await client.websocket.send_json(payload)
            except Exception:
                for conversation_id, room in list(self._conversation_rooms.items()):
                    if client in room:
                        self.disconnect(conversation_id, client)


class UserSocketHub:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    def connect(self, user_id: int, websocket: WebSocket) -> None:
        self._connections[user_id].add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        sockets = self._connections.get(user_id)
        if not sockets:
            return
        if websocket in sockets:
            sockets.remove(websocket)
        if not sockets:
            self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: int, payload: dict[str, Any]) -> None:
        targets = list(self._connections.get(user_id, set()))
        for websocket in targets:
            try:
                await websocket.send_json(payload)
            except Exception:
                self.disconnect(user_id, websocket)
