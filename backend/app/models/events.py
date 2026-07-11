"""Event models for the TrueCandidate meeting event system with strict input validation."""

from __future__ import annotations

import html
import re
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


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
    participant_id: Optional[str] = Field(default=None, max_length=64)
    timestamp: float = Field(description="Seconds since meeting start", ge=0.0, le=86400.0)
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("participant_id")
    @classmethod
    def validate_participant_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            # Enforce strict alphanumeric format to prevent injections
            if not re.match(r"^[a-zA-Z0-9_-]+$", v):
                raise ValueError("participant_id must be alphanumeric, dashes, or underscores only")
        return v

    @field_validator("data")
    @classmethod
    def sanitize_and_limit_data(cls, v: dict[str, Any]) -> dict[str, Any]:
        # Enforce maximum data payload structure size to avoid memory exhaustion (DoS)
        if len(v) > 20:
            raise ValueError("Too many data attributes in event payload")

        sanitized = {}
        for key, val in v.items():
            if len(str(key)) > 64:
                raise ValueError("Data key name exceeds maximum length")
            
            # Sanitize text fields to prevent HTML/XSS injections
            if isinstance(val, str):
                if len(val) > 4000:
                    raise ValueError("String value in data payload exceeds 4000 characters")
                sanitized[key] = html.escape(val)
            else:
                sanitized[key] = val
        return sanitized

    class Config:
        use_enum_values = True


class TranscriptChunk(BaseModel):
    """A speaker-attributed transcript segment."""
    speaker_id: str = Field(max_length=64)
    text: str = Field(max_length=4000)
    timestamp: float = Field(ge=0.0)
    duration: Optional[float] = Field(default=None, ge=0.0)

    @field_validator("speaker_id")
    @classmethod
    def validate_speaker_id(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("speaker_id must be alphanumeric, dashes, or underscores only")
        return v

    @field_validator("text")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        return html.escape(v)


class CalendarMetadata(BaseModel):
    """External metadata from the calendar invite."""
    candidate_name: str = Field(max_length=100)
    candidate_email: Optional[str] = Field(default=None, max_length=100)
    interviewer_names: list[str] = Field(default_factory=list)
    interviewer_emails: list[str] = Field(default_factory=list)
    scheduled_time: Optional[str] = Field(default=None, max_length=50)
    position: Optional[str] = Field(default=None, max_length=100)
    company: Optional[str] = Field(default=None, max_length=100)

    @field_validator("candidate_name")
    @classmethod
    def sanitize_candidate_name(cls, v: str) -> str:
        return html.escape(v)

    @field_validator("candidate_email")
    @classmethod
    def sanitize_candidate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", v):
                raise ValueError("Invalid email format")
            return html.escape(v)
        return v

    @field_validator("interviewer_names")
    @classmethod
    def sanitize_interviewer_names(cls, v: list[str]) -> list[str]:
        if len(v) > 20:
            raise ValueError("Too many interviewers specified")
        return [html.escape(name)[:100] for name in v]


class MeetingInfo(BaseModel):
    """Basic meeting information."""
    meeting_id: str = Field(max_length=64)
    title: Optional[str] = Field(default=None, max_length=100)
    platform: Optional[str] = Field(default="mock", max_length=50)
    start_time: Optional[datetime] = None
    calendar: Optional[CalendarMetadata] = None

    @field_validator("meeting_id")
    @classmethod
    def validate_meeting_id(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("meeting_id must be alphanumeric, dashes, or underscores only")
        return v
