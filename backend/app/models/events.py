"""Event models for the TrueCandidate meeting event system."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """All possible meeting event types."""
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    DISPLAY_NAME_CHANGED = "display_name_changed"
    SPEAKING_STARTED = "speaking_started"
    SPEAKING_STOPPED = "speaking_stopped"
    WEBCAM_ENABLED = "webcam_enabled"
    WEBCAM_DISABLED = "webcam_disabled"
    TRANSCRIPT_CHUNK = "transcript_chunk"
    SCREEN_SHARE_STARTED = "screen_share_started"
    SCREEN_SHARE_STOPPED = "screen_share_stopped"
    MEETING_STARTED = "meeting_started"
    MEETING_ENDED = "meeting_ended"


class MeetingEvent(BaseModel):
    """A normalized meeting event emitted by any connector."""
    event_type: EventType
    participant_id: Optional[str] = None
    timestamp: float = Field(description="Seconds since meeting start")
    data: dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class TranscriptChunk(BaseModel):
    """A speaker-attributed transcript segment."""
    speaker_id: str
    text: str
    timestamp: float
    duration: Optional[float] = None


class CalendarMetadata(BaseModel):
    """External metadata from the calendar invite."""
    candidate_name: str
    candidate_email: Optional[str] = None
    interviewer_names: list[str] = Field(default_factory=list)
    interviewer_emails: list[str] = Field(default_factory=list)
    scheduled_time: Optional[str] = None
    position: Optional[str] = None
    company: Optional[str] = None


class MeetingInfo(BaseModel):
    """Basic meeting information."""
    meeting_id: str
    title: Optional[str] = None
    platform: Optional[str] = "mock"
    start_time: Optional[datetime] = None
    calendar: Optional[CalendarMetadata] = None
