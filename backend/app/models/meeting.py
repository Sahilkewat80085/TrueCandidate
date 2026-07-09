"""Meeting session models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .events import CalendarMetadata, MeetingEvent, TranscriptChunk
from .participant import ParticipantState
from .evidence import EvidenceItem
from .prediction import CandidatePrediction, ConfidencePoint


class MeetingStatus(str, Enum):
    """Status of a meeting session."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    ERROR = "error"


class MeetingSession(BaseModel):
    """Complete state of a meeting session."""
    meeting_id: str
    status: MeetingStatus = MeetingStatus.PENDING
    scenario_id: Optional[str] = None
    start_time: Optional[datetime] = None
    current_time: float = 0.0  # seconds since start

    # Participants
    participants: dict[str, ParticipantState] = Field(default_factory=dict)

    # Data
    transcript: list[TranscriptChunk] = Field(default_factory=list)
    events: list[MeetingEvent] = Field(default_factory=list)
    evidence_log: list[EvidenceItem] = Field(default_factory=list)

    # Calendar
    calendar: Optional[CalendarMetadata] = None

    # Prediction
    current_prediction: Optional[CandidatePrediction] = None
    confidence_timeline: list[ConfidencePoint] = Field(default_factory=list)

    class Config:
        use_enum_values = True
