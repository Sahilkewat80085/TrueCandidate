"""Mock Meeting Connector — replays scenario files to simulate real meetings.

This connector serves triple duty:
1. DEMO: Realistic meeting simulation for the dashboard
2. TESTING: Deterministic replay for unit/integration tests
3. EVALUATION: Automated scenario evaluation for accuracy metrics
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

from backend.app.connectors.base import MeetingConnector
from backend.app.models.events import (
    CalendarMetadata,
    EventType,
    MeetingEvent,
    MeetingInfo,
)

logger = logging.getLogger(__name__)


class MockMeetingConnector(MeetingConnector):
    """Replays pre-defined scenario JSON files as meeting events."""

    def __init__(self, scenario_dir: str = "scenarios", speed: float = 1.0):
        self.scenario_dir = Path(scenario_dir)
        self.speed = speed
        self._meeting_info: Optional[MeetingInfo] = None
        self._calendar: Optional[CalendarMetadata] = None
        self._events: list[dict] = []
        self._callbacks: list[Callable[[MeetingEvent], None]] = []
        self._active = False
        self._task: Optional[asyncio.Task] = None
        self._event_queue: asyncio.Queue[MeetingEvent] = asyncio.Queue()
        self._scenario_data: dict = {}

    async def connect(self, meeting_id: str) -> MeetingInfo:
        """Load a scenario file and prepare for replay."""
        scenario_path = self.scenario_dir / f"{meeting_id}.json"

        if not scenario_path.exists():
            # Try looking for scenario by ID pattern
            for f in self.scenario_dir.glob("*.json"):
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("scenario_id") == meeting_id:
                    scenario_path = f
                    break

        if not scenario_path.exists():
            raise FileNotFoundError(f"Scenario not found: {meeting_id}")

        self._scenario_data = json.loads(scenario_path.read_text(encoding="utf-8"))
        self._events = self._scenario_data.get("events", [])

        # Build calendar metadata
        cal_data = self._scenario_data.get("calendar_metadata", {})
        self._calendar = CalendarMetadata(**cal_data) if cal_data else None

        self._meeting_info = MeetingInfo(
            meeting_id=meeting_id,
            title=self._scenario_data.get("title", "Mock Meeting"),
            platform="mock",
            calendar=self._calendar,
        )

        logger.info(f"Loaded scenario: {self._scenario_data.get('title')} with {len(self._events)} events")
        return self._meeting_info

    async def disconnect(self) -> None:
        """Stop and clean up."""
        await self.stop()
        self._meeting_info = None
        self._events = []

    async def get_calendar_metadata(self) -> Optional[CalendarMetadata]:
        return self._calendar

    async def get_meeting_info(self) -> MeetingInfo:
        if not self._meeting_info:
            raise RuntimeError("Not connected to a meeting")
        return self._meeting_info

    def subscribe_events(self, callback: Callable[[MeetingEvent], None]) -> None:
        self._callbacks.append(callback)

    async def stream_events(self) -> AsyncIterator[MeetingEvent]:
        """Yield events as they are replayed."""
        while self._active or not self._event_queue.empty():
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                yield event
            except asyncio.TimeoutError:
                continue

    async def start(self) -> None:
        """Start replaying events with realistic timing."""
        if self._active:
            return
        self._active = True
        self._task = asyncio.create_task(self._replay_events())
        logger.info("Mock connector started — replaying events")

    async def stop(self) -> None:
        """Stop event replay."""
        self._active = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Mock connector stopped")

    def is_active(self) -> bool:
        return self._active

    def get_scenario_metadata(self) -> dict:
        """Return scenario metadata for evaluation."""
        return {
            "scenario_id": self._scenario_data.get("scenario_id", ""),
            "title": self._scenario_data.get("title", ""),
            "description": self._scenario_data.get("description", ""),
            "expected_candidate": self._scenario_data.get("expected_candidate", ""),
            "difficulty": self._scenario_data.get("difficulty", "medium"),
        }

    async def _replay_events(self) -> None:
        """Replay events with timing delays."""
        prev_time = 0.0

        for event_data in self._events:
            if not self._active:
                break

            event_time = event_data.get("time", 0)
            delay = (event_time - prev_time) / self.speed

            if delay > 0:
                await asyncio.sleep(delay)

            if not self._active:
                break

            event = self._build_event(event_data)
            if event:
                # Put in queue for stream_events
                await self._event_queue.put(event)

                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(event)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")

            prev_time = event_time

        self._active = False
        logger.info("Scenario replay completed")

    def _build_event(self, data: dict) -> Optional[MeetingEvent]:
        """Convert raw scenario event data to a MeetingEvent."""
        try:
            event_type = data.get("type", "")
            event_data = {}

            # Copy all fields except type, time, participant_id
            for key, value in data.items():
                if key not in ("type", "time", "participant_id"):
                    event_data[key] = value

            return MeetingEvent(
                event_type=event_type,
                participant_id=data.get("participant_id"),
                timestamp=data.get("time", 0),
                data=event_data,
            )
        except Exception as e:
            logger.warning(f"Failed to build event: {e} from {data}")
            return None


def list_scenarios(scenario_dir: str = "scenarios") -> list[dict]:
    """List all available scenario files."""
    path = Path(scenario_dir)
    scenarios = []

    if not path.exists():
        return scenarios

    for f in sorted(path.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            scenarios.append({
                "id": data.get("scenario_id", f.stem),
                "title": data.get("title", f.stem),
                "description": data.get("description", ""),
                "difficulty": data.get("difficulty", "medium"),
                "filename": f.name,
            })
        except Exception as e:
            logger.warning(f"Failed to load scenario {f}: {e}")

    return scenarios
