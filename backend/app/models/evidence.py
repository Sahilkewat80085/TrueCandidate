"""Evidence models for the fusion engine."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SignalType(str, Enum):
    """Types of evidence signals."""
    NAME_SIMILARITY = "name_similarity"
    CALENDAR_MATCH = "calendar_match"
    SPEECH_PATTERN = "speech_pattern"
    TRANSCRIPT_EVIDENCE = "transcript_evidence"
    BEHAVIORAL = "behavioral"
    TEMPORAL = "temporal"
    LLM_REASONING = "llm_reasoning"
    PENALTY = "penalty"


class EvidenceItem(BaseModel):
    """A single piece of evidence produced by a signal analyzer."""
    signal_type: SignalType
    participant_id: str
    score: float = Field(ge=-1.0, le=1.0, description="Evidence strength: -1 to 1")
    weight: float = Field(ge=0.0, description="Importance weight of this signal type")
    confidence: float = Field(ge=0.0, le=1.0, description="How confident is this specific evidence")
    reason: str = Field(description="Human-readable explanation")
    timestamp: float = Field(description="When this evidence was produced")
    details: dict = Field(default_factory=dict, description="Additional details for debugging")

    class Config:
        use_enum_values = True


class EvidenceSnapshot(BaseModel):
    """All evidence collected for a specific participant at a point in time."""
    participant_id: str
    display_name: str
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    raw_score: float = 0.0
    normalized_confidence: float = 0.0
    timestamp: float = 0.0
