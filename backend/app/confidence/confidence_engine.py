"""Confidence Engine — converts raw fusion scores into calibrated confidence.

Features:
- Temporal smoothing (exponential moving average) to prevent oscillations
- Confidence level thresholds (low, medium, high, very_high)
- Full timeline tracking for visualization
- Never permanently locks — can always decrease with counter-evidence
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.app.config import AppConfig
from backend.app.models.prediction import ConfidencePoint

logger = logging.getLogger(__name__)


class ConfidenceEngine:
    """Manages calibrated confidence scores with temporal smoothing."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        conf = self.config.confidence

        self._alpha = conf.smoothing_alpha  # EMA smoothing factor
        self._thresholds = {
            "very_high": conf.high_threshold,     # 0.9
            "high": conf.medium_threshold,         # 0.7
            "medium": conf.low_threshold,          # 0.4
            "low": 0.0,
        }

        # Per-participant smoothed confidence
        self._smoothed: dict[str, float] = {}

        # Timeline
        self._timeline: list[ConfidencePoint] = []

        # Track history for stability metrics
        self._history: dict[str, list[float]] = {}

    def update(
        self,
        probabilities: dict[str, float],
        timestamp: float,
        event_description: Optional[str] = None,
    ) -> dict[str, float]:
        """Update confidence scores from fusion engine probabilities.
        
        Args:
            probabilities: Raw probabilities from fusion engine (sum to 1)
            timestamp: Current meeting time
            event_description: Optional description of what triggered this update
            
        Returns:
            Dict of participant_id -> smoothed confidence
        """
        result = {}

        for pid, raw_prob in probabilities.items():
            # Apply exponential moving average smoothing
            if pid in self._smoothed:
                smoothed = self._alpha * raw_prob + (1 - self._alpha) * self._smoothed[pid]
            else:
                smoothed = raw_prob

            self._smoothed[pid] = smoothed
            result[pid] = smoothed

            # Track history
            if pid not in self._history:
                self._history[pid] = []
            self._history[pid].append(smoothed)

            # Add to timeline
            self._timeline.append(ConfidencePoint(
                timestamp=timestamp,
                participant_id=pid,
                confidence=smoothed,
                event_description=event_description,
            ))

        return result

    def get_confidence(self, participant_id: str) -> float:
        """Get current smoothed confidence for a participant."""
        return self._smoothed.get(participant_id, 0.0)

    def get_confidence_level(self, participant_id: str) -> str:
        """Get the confidence level label for a participant."""
        conf = self.get_confidence(participant_id)
        if conf >= self._thresholds["very_high"]:
            return "very_high"
        elif conf >= self._thresholds["high"]:
            return "high"
        elif conf >= self._thresholds["medium"]:
            return "medium"
        return "low"

    def get_all_confidences(self) -> dict[str, float]:
        """Get all current confidence scores."""
        return dict(self._smoothed)

    def get_timeline(self, participant_id: Optional[str] = None) -> list[ConfidencePoint]:
        """Get confidence timeline, optionally filtered by participant."""
        if participant_id:
            return [p for p in self._timeline if p.participant_id == participant_id]
        return list(self._timeline)

    def get_top_candidate(self) -> Optional[tuple[str, float]]:
        """Return participant with highest smoothed confidence."""
        if not self._smoothed:
            return None
        top_pid = max(self._smoothed, key=self._smoothed.get)
        return (top_pid, self._smoothed[top_pid])

    def get_stability(self, participant_id: str, window: int = 5) -> float:
        """Compute confidence stability (low variance = stable).
        
        Returns value 0-1 where 1 is very stable.
        """
        history = self._history.get(participant_id, [])
        if len(history) < window:
            return 0.0

        recent = history[-window:]
        mean = sum(recent) / len(recent)
        variance = sum((x - mean) ** 2 for x in recent) / len(recent)

        # Convert variance to stability score (0-1)
        return max(0.0, 1.0 - variance * 10)

    def get_trend(self, participant_id: str, window: int = 5) -> str:
        """Get confidence trend: 'rising', 'falling', or 'stable'."""
        history = self._history.get(participant_id, [])
        if len(history) < 2:
            return "stable"

        recent = history[-window:]
        if len(recent) < 2:
            return "stable"

        diff = recent[-1] - recent[0]
        if diff > 0.05:
            return "rising"
        elif diff < -0.05:
            return "falling"
        return "stable"

    def reset(self) -> None:
        """Reset for a new meeting."""
        self._smoothed.clear()
        self._timeline.clear()
        self._history.clear()
