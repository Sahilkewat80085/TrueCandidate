"""Participant models for tracking meeting participants."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ParticipantRole(str, Enum):
    """Inferred role of a participant."""
    UNKNOWN = "unknown"
    CANDIDATE = "candidate"
    INTERVIEWER = "interviewer"
    OBSERVER = "observer"


class ParticipantState(BaseModel):
    """Current state of a participant in the meeting."""
    participant_id: str
    display_name: str
    display_name_history: list[str] = Field(default_factory=list)
    is_active: bool = True
    webcam_on: bool = False
    is_speaking: bool = False
    is_screen_sharing: bool = False

    # Timing
    join_time: float = 0.0
    leave_time: Optional[float] = None

    # Aggregated stats
    total_speaking_duration: float = 0.0
    speaking_segments: int = 0
    webcam_on_duration: float = 0.0
    transcript_word_count: int = 0

    # Identification
    inferred_role: ParticipantRole = ParticipantRole.UNKNOWN
    candidate_confidence: float = 0.0

    # Internal tracking
    _speaking_start: Optional[float] = None
    _webcam_start: Optional[float] = None

    class Config:
        underscore_attrs_are_private = True
