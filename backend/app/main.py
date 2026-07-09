"""TrueCandidate — FastAPI Application Entry Point.

This is the main FastAPI application that ties together:
- REST API for meeting management
- WebSocket for real-time updates
- Session manager for meeting lifecycle
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import health, meetings, scenarios
from backend.app.api.websocket import ws_manager
from backend.app.config import load_config
from backend.app.core.session import MeetingSessionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class AppState:
    """Global application state."""

    def __init__(self):
        self.config = load_config()
        self.session_manager = MeetingSessionManager(self.config)

    async def on_meeting_update(self, meeting_id: str, prediction, event, evidence):
        """Callback when a meeting prediction updates — broadcasts via WebSocket."""
        try:
            await ws_manager.broadcast(meeting_id, {
                "type": "prediction_update",
                "meeting_id": meeting_id,
                "prediction": prediction.model_dump() if prediction else None,
                "event": event.model_dump() if event else None,
                "evidence": [e.model_dump() for e in evidence] if evidence else [],
            })
        except Exception as e:
            logger.error(f"Failed to broadcast update: {e}")


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("🚀 TrueCandidate starting up...")
    logger.info(f"   LLM enabled: {app_state.config.llm.enabled}")
    logger.info(f"   Scenario speed: {app_state.config.scenario_speed}x")
    yield
    logger.info("TrueCandidate shutting down...")


app = FastAPI(
    title="TrueCandidate",
    description="AI-powered interview candidate identification system for Sherlock",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_state.config.cors_origins + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health.router)
app.include_router(meetings.router)
app.include_router(scenarios.router)


# WebSocket endpoint
@app.websocket("/ws/{meeting_id}")
async def websocket_endpoint(websocket: WebSocket, meeting_id: str):
    """WebSocket for real-time meeting updates."""
    await ws_manager.connect(websocket, meeting_id)

    try:
        # Send initial state if session exists
        prediction = app_state.session_manager.get_prediction(meeting_id)
        if prediction:
            await ws_manager.send_personal(websocket, {
                "type": "initial_state",
                "prediction": prediction.model_dump(),
            })

        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                # Client can send commands (e.g., request current state)
                if data == "ping":
                    await ws_manager.send_personal(websocket, {"type": "pong"})
                elif data == "get_prediction":
                    prediction = app_state.session_manager.get_prediction(meeting_id)
                    if prediction:
                        await ws_manager.send_personal(websocket, {
                            "type": "prediction_update",
                            "prediction": prediction.model_dump(),
                        })
            except WebSocketDisconnect:
                break
    finally:
        ws_manager.disconnect(websocket, meeting_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=app_state.config.host,
        port=app_state.config.port,
        reload=True,
    )
