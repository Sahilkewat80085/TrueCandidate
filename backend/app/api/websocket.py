"""WebSocket handler for real-time updates to the frontend."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time streaming."""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}  # meeting_id -> connections

    async def connect(self, websocket: WebSocket, meeting_id: str) -> None:
        """Accept a new WebSocket connection for a meeting."""
        await websocket.accept()
        if meeting_id not in self._connections:
            self._connections[meeting_id] = []
        self._connections[meeting_id].append(websocket)
        logger.info(f"WebSocket connected for meeting {meeting_id} (total: {len(self._connections[meeting_id])})")

    def disconnect(self, websocket: WebSocket, meeting_id: str) -> None:
        """Remove a WebSocket connection."""
        if meeting_id in self._connections:
            if websocket in self._connections[meeting_id]:
                self._connections[meeting_id].remove(websocket)
            if not self._connections[meeting_id]:
                del self._connections[meeting_id]
        logger.info(f"WebSocket disconnected for meeting {meeting_id}")

    async def broadcast(self, meeting_id: str, message: dict) -> None:
        """Broadcast a message to all connected clients for a meeting."""
        if meeting_id not in self._connections:
            return

        disconnected = []
        data = json.dumps(message, default=str)

        for ws in self._connections[meeting_id]:
            try:
                await ws.send_text(data)
            except Exception:
                disconnected.append(ws)

        # Clean up disconnected
        for ws in disconnected:
            self.disconnect(ws, meeting_id)

    async def send_personal(self, websocket: WebSocket, message: dict) -> None:
        """Send a message to a specific client."""
        try:
            await websocket.send_text(json.dumps(message, default=str))
        except Exception as e:
            logger.warning(f"Failed to send personal message: {e}")

    def get_connection_count(self, meeting_id: str) -> int:
        """Get the number of active connections for a meeting."""
        return len(self._connections.get(meeting_id, []))


# Global connection manager instance
ws_manager = ConnectionManager()
