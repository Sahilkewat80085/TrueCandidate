"""Abstract Meeting Connector interface.

All platform-specific connectors must implement this interface.
The AI engine ONLY interacts with meetings through this abstraction,
making it completely platform-independent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, Callable, Optional

from backend.app.models.events import CalendarMetadata, MeetingEvent, MeetingInfo


class MeetingConnector(ABC):
    """Abstract interface for meeting data connectors.
    
    Implementations:
        - MockMeetingConnector: Simulates meetings from scenario files
        - Future: GoogleMeetConnector, ZoomConnector, TeamsConnector, RecallAIConnector
    """

    @abstractmethod
    async def connect(self, meeting_id: str) -> MeetingInfo:
        """Connect to a meeting and return basic meeting info."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the current meeting."""
        ...

    @abstractmethod
    async def get_calendar_metadata(self) -> Optional[CalendarMetadata]:
        """Get external calendar metadata for the meeting."""
        ...

    @abstractmethod
    async def get_meeting_info(self) -> MeetingInfo:
        """Get current meeting information."""
        ...

    @abstractmethod
    def subscribe_events(self, callback: Callable[[MeetingEvent], None]) -> None:
        """Register a callback for meeting events."""
        ...

    @abstractmethod
    async def stream_events(self) -> AsyncIterator[MeetingEvent]:
        """Stream meeting events as they occur."""
        ...

    @abstractmethod
    async def start(self) -> None:
        """Start emitting events."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop emitting events."""
        ...

    @abstractmethod
    def is_active(self) -> bool:
        """Check if the connector is actively streaming."""
        ...
