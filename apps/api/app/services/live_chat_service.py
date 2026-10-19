from __future__ import annotations

import json
import logging
from typing import Any
from fastapi import WebSocket

logger = logging.getLogger("live_chat")


class LiveChatConnectionManager:
    def __init__(self):
        # Map: session_code -> list of client WebSockets
        self.client_connections: dict[str, list[WebSocket]] = {}
        # Map: staff_user_id -> list of staff WebSockets
        self.staff_connections: dict[int, list[WebSocket]] = {}

    async def connect_client(self, session_code: str, websocket: WebSocket):
        await websocket.accept()
        if session_code not in self.client_connections:
            self.client_connections[session_code] = []
        self.client_connections[session_code].append(websocket)
        logger.info(f"[LiveChat] Client connected to session: {session_code}")

    def disconnect_client(self, session_code: str, websocket: WebSocket):
        if session_code in self.client_connections:
            if websocket in self.client_connections[session_code]:
                self.client_connections[session_code].remove(websocket)
            if not self.client_connections[session_code]:
                del self.client_connections[session_code]
        logger.info(f"[LiveChat] Client disconnected from session: {session_code}")

    async def connect_staff(self, staff_id: int, websocket: WebSocket):
        await websocket.accept()
        if staff_id not in self.staff_connections:
            self.staff_connections[staff_id] = []
        self.staff_connections[staff_id].append(websocket)
        logger.info(f"[LiveChat] Staff {staff_id} connected")
        # Thông báo tới các client là có nhân viên đang trực
        await self.broadcast_staff_status_to_all()

    def disconnect_staff(self, staff_id: int, websocket: WebSocket):
        if staff_id in self.staff_connections:
            if websocket in self.staff_connections[staff_id]:
                self.staff_connections[staff_id].remove(websocket)
            if not self.staff_connections[staff_id]:
                del self.staff_connections[staff_id]
        logger.info(f"[LiveChat] Staff {staff_id} disconnected")

    def is_staff_online(self, staff_id: int) -> bool:
        return bool(self.staff_connections.get(staff_id))

    def is_any_staff_online(self) -> bool:
        """Kiểm tra thực tế xem có bất kỳ nhân viên nào đang online (có active socket) không."""
        return any(len(sockets) > 0 for sockets in self.staff_connections.values())

    def get_online_staff_count(self) -> int:
        return sum(1 for sockets in self.staff_connections.values() if len(sockets) > 0)

    async def broadcast_staff_status_to_all(self):
        payload = {
            "type": "STAFF_STATUS",
            "is_online": self.is_any_staff_online(),
            "online_count": self.get_online_staff_count(),
        }
        await self.broadcast_to_all_clients(payload)

    async def broadcast_to_session(self, session_code: str, message_data: dict[str, Any], assigned_staff_id: int | None = None):
        """Gửi message tới client trong session và nhân viên phụ trách (hoặc tất cả nhân viên nếu chưa gán)."""
        payload_str = json.dumps(message_data, default=str)

        # 1. Gửi cho client
        if session_code in self.client_connections:
            dead_sockets = []
            for ws in self.client_connections[session_code]:
                try:
                    await ws.send_text(payload_str)
                except Exception:
                    dead_sockets.append(ws)
            for ws in dead_sockets:
                self.disconnect_client(session_code, ws)

        # 2. Gửi cho nhân viên
        if assigned_staff_id and assigned_staff_id in self.staff_connections:
            await self._send_to_staff_id(assigned_staff_id, payload_str)
        else:
            # Nếu chưa có staff nào gán, gửi cho toàn bộ staff đang online
            for staff_id in list(self.staff_connections.keys()):
                await self._send_to_staff_id(staff_id, payload_str)

    async def _send_to_staff_id(self, staff_id: int, payload_str: str):
        if staff_id in self.staff_connections:
            dead = []
            for ws in self.staff_connections[staff_id]:
                try:
                    await ws.send_text(payload_str)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.disconnect_staff(staff_id, ws)

    async def broadcast_to_staff(self, event_type: str, data: dict[str, Any], target_staff_id: int | None = None):
        """Phát sự kiện tới nhân viên (phiên mới, cập nhật phiên, đóng phiên)."""
        payload = {"type": event_type, "data": data}
        payload_str = json.dumps(payload, default=str)

        if target_staff_id:
            await self._send_to_staff_id(target_staff_id, payload_str)
        else:
            for s_id in list(self.staff_connections.keys()):
                await self._send_to_staff_id(s_id, payload_str)

    async def broadcast_to_all_clients(self, data: dict[str, Any]):
        payload_str = json.dumps(data, default=str)
        for s_code, sockets in list(self.client_connections.items()):
            dead = []
            for ws in sockets:
                try:
                    await ws.send_text(payload_str)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.disconnect_client(s_code, ws)


# Singleton manager instance
chat_manager = LiveChatConnectionManager()
