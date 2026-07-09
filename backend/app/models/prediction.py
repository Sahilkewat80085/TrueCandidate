"""Prediction and confidence models."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ConfidenceLevel(str):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ReasonItem(BaseModel):
    """A single reason contributing to the prediction."""
    signal: str
    impact: str  # e.g., "+20", "-5"
    reason: str
    icon: str = "info"  # "positive", "negative", "warning", "info"


class ParticipantPrediction(BaseModel):
    """Prediction details for a single participant."""
    participant_id: str
    display_name: str
    confidence: float = 0.0
    role: str = "unknown"
    top_reasons: list[ReasonItem] = Field(default_factory=list)


class CandidatePrediction(BaseModel):
    """The current candidate prediction with full explanation."""
    meeting_id: str
    current_candidate_id: Optional[str] = None
    current_candidate_name: Optional[str] = None
    confidence: float = 0.0
    confidence_level: str = "low"
    top_reasons: list[ReasonItem] = Field(default_factory=list)
    all_participants: list[ParticipantPrediction] = Field(default_factory=list)
    uncertainty_factors: list[str] = Field(default_factory=list)
    timestamp: float = 0.0


class ConfidencePoint(BaseModel):
    """A single point in the confidence timeline."""
    timestamp: float
    participant_id: str
    confidence: float
    event_description: Optional[str] = None


class ConfidenceTimeline(BaseModel):
    """Full confidence timeline for a meeting."""
    meeting_id: str
    points: list[ConfidencePoint] = Field(default_factory=list)
