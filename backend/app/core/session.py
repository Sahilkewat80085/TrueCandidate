"""Meeting session manager — coordinates connector and engine lifecycle."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Callable, Optional

from backend.app.config import AppConfig
from backend.app.connectors.mock_connector import MockMeetingConnector, list_scenarios
from backend.app.core.engine import IdentificationEngine
from backend.app.models.events import MeetingEvent, CalendarMetadata
from backend.app.models.prediction import CandidatePrediction

logger = logging.getLogger(__name__)


class MeetingSessionManager:
    """Manages active meeting sessions with their connectors and engines."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self._sessions: dict[str, dict] = {}
        self._scenario_dir = str(Path(__file__).parent.parent.parent / "scenarios")

    def list_scenarios(self) -> list[dict]:
        """List available scenarios."""
        return list_scenarios(self._scenario_dir)

    async def start_scenario(
        self,
        scenario_id: str,
        update_callback: Optional[Callable] = None,
        speed: float = 1.0,
    ) -> str:
        """Start a scenario simulation and return meeting ID."""
        meeting_id = f"meeting_{uuid.uuid4().hex[:8]}"

        # Create connector
        connector = MockMeetingConnector(
            scenario_dir=self._scenario_dir,
            speed=speed or self.config.scenario_speed,
        )

        # Load scenario
        await connector.connect(scenario_id)

        # Create engine
        engine = IdentificationEngine(self.config)
        engine.meeting_id = meeting_id

        # Set calendar metadata
        calendar = await connector.get_calendar_metadata()
        if calendar:
            engine.set_calendar(calendar)

        # Store session
        self._sessions[meeting_id] = {
            "connector": connector,
            "engine": engine,
            "scenario_id": scenario_id,
            "scenario_meta": connector.get_scenario_metadata(),
            "task": None,
            "update_callback": update_callback,
            "events": [],
            "predictions": [],
        }

        # Register engine callback
        if update_callback:
            def sync_wrapper(pred, evt, evid):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(update_callback(meeting_id, pred, evt, evid))
                except RuntimeError:
                    pass
            engine.on_update(sync_wrapper)

        # Start replay in background
        session = self._sessions[meeting_id]
        session["task"] = asyncio.create_task(
            self._run_session(meeting_id)
        )

        logger.info(f"Started scenario '{scenario_id}' as meeting '{meeting_id}'")
        return meeting_id

    async def start_custom_meeting(
        self,
        calendar: CalendarMetadata,
        update_callback: Optional[Callable] = None,
    ) -> str:
        """Start an empty custom meeting session to accept live external events."""
        meeting_id = f"live_{uuid.uuid4().hex[:8]}"

        # Create engine
        engine = IdentificationEngine(self.config)
        engine.meeting_id = meeting_id
        engine.set_calendar(calendar)

        # Store session
        self._sessions[meeting_id] = {
            "connector": None,  # Externally pushed
            "engine": engine,
            "scenario_id": "live_meet",
            "scenario_meta": {
                "scenario_id": "live_meet",
                "title": "Live Google Meet",
                "description": "Streaming events directly from Google Meet Chrome Extension",
                "difficulty": "live",
            },
            "task": None,
            "update_callback": update_callback,
            "events": [],
            "predictions": [],
        }

        # Register engine callback
        if update_callback:
            def sync_wrapper(pred, evt, evid):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(update_callback(meeting_id, pred, evt, evid))
                except RuntimeError:
                    pass
            engine.on_update(sync_wrapper)

        logger.info(f"Started custom live meeting: {meeting_id}")
        return meeting_id

    async def _run_session(self, meeting_id: str) -> None:
        """Run a meeting session — process events from connector through engine."""
        session = self._sessions.get(meeting_id)
        if not session:
            return

        connector: MockMeetingConnector = session["connector"]
        engine: IdentificationEngine = session["engine"]

        await connector.start()

        async for event in connector.stream_events():
            try:
                prediction = engine.process_event(event)
                session["events"].append(event)
                if prediction:
                    session["predictions"].append(prediction)
            except Exception as e:
                logger.error(f"Error processing event in {meeting_id}: {e}", exc_info=True)

        logger.info(f"Session {meeting_id} completed")

    async def stop_session(self, meeting_id: str) -> None:
        """Stop an active meeting session."""
        session = self._sessions.get(meeting_id)
        if not session:
            return

        connector = session["connector"]
        if connector:
            await connector.stop()

        task = session.get("task")
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info(f"Stopped session {meeting_id}")

    def get_session(self, meeting_id: str) -> Optional[dict]:
        """Get session data."""
        return self._sessions.get(meeting_id)

    def get_engine(self, meeting_id: str) -> Optional[IdentificationEngine]:
        """Get the engine for a meeting."""
        session = self._sessions.get(meeting_id)
        return session["engine"] if session else None

    def get_prediction(self, meeting_id: str) -> Optional[CandidatePrediction]:
        """Get current prediction for a meeting."""
        engine = self.get_engine(meeting_id)
        if engine:
            return engine.get_current_prediction()
        return None

    def list_active_sessions(self) -> list[dict]:
        """List all active sessions."""
        result = []
        for mid, session in self._sessions.items():
            result.append({
                "meeting_id": mid,
                "scenario_id": session["scenario_id"],
                "scenario_meta": session["scenario_meta"],
                "is_active": session["connector"].is_active() if session["connector"] else True,
                "event_count": len(session["events"]),
            })
        return result
