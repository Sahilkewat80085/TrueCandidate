"""Fusion Engine — combines evidence from all analyzers into unified participant scores.

Implements weighted Bayesian evidence fusion:
1. Initialize with uniform prior (1/N per participant)
2. For each evidence item, compute likelihood ratio
3. Update posterior using Bayes' rule
4. Apply temporal decay to older evidence
5. Normalize across all participants
"""

from __future__ import annotations

import math
import logging
from typing import Optional

from backend.app.config import AppConfig
from backend.app.models.evidence import EvidenceItem
from backend.app.models.participant import ParticipantState

logger = logging.getLogger(__name__)


class FusionEngine:
    """Weighted Bayesian evidence fusion engine."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()

        # Per-participant log-odds (more numerically stable than raw probabilities)
        self._log_odds: dict[str, float] = {}

        # Evidence history for temporal decay
        self._evidence_history: list[EvidenceItem] = []

        # Track last evidence timestamp per participant for O(1) decay lookup
        self._last_evidence_time: dict[str, float] = {}

        # Current time for decay calculations
        self._current_time: float = 0.0

    def add_participant(self, participant_id: str) -> None:
        """Add a participant with uniform prior."""
        if participant_id not in self._log_odds:
            self._log_odds[participant_id] = 0.0  # Log-odds 0 = 50% prior
            self._last_evidence_time[participant_id] = 0.0
            logger.debug(f"Added participant {participant_id} to fusion engine")

    def remove_participant(self, participant_id: str) -> None:
        """Remove a participant."""
        self._log_odds.pop(participant_id, None)
        self._last_evidence_time.pop(participant_id, None)

    def update(self, evidence: EvidenceItem) -> dict[str, float]:
        """Process a single evidence item and return updated probabilities.
        
        Args:
            evidence: The evidence item to incorporate
            
        Returns:
            Dict of participant_id -> probability (0 to 1, sums to 1)
        """
        self._current_time = max(self._current_time, evidence.timestamp)
        self._evidence_history.append(evidence)

        pid = evidence.participant_id
        if pid not in self._log_odds:
            self.add_participant(pid)

        self._last_evidence_time[pid] = evidence.timestamp

        # Compute log-likelihood ratio from evidence
        # score in [-1, 1], weight controls importance, confidence modulates strength
        effective_score = evidence.score * evidence.confidence
        weight_factor = evidence.weight / 20.0  # Normalize weight (20 is reference)
        
        # Convert to log-odds update
        # A score of 1.0 with full confidence and weight should give strong update
        log_lr = effective_score * weight_factor * 2.0

        # Apply update to the specific participant
        self._log_odds[pid] += log_lr

        # Clamp to prevent extreme values
        self._log_odds[pid] = max(min(self._log_odds[pid], 10.0), -10.0)

        return self.get_probabilities()

    def update_batch(self, evidence_items: list[EvidenceItem]) -> dict[str, float]:
        """Process multiple evidence items at once."""
        for item in evidence_items:
            self.update(item)
        return self.get_probabilities()

    def get_probabilities(self) -> dict[str, float]:
        """Convert log-odds to normalized probabilities with temporal decay."""
        if not self._log_odds:
            return {}

        # Apply temporal decay
        halflife = self.config.confidence.temporal_decay_halflife
        decayed_odds = {}

        for pid, log_odd in self._log_odds.items():
            last_time = self._last_evidence_time.get(pid, 0.0)
            idle_time = max(0.0, self._current_time - last_time)
            
            if idle_time > 0.0 and halflife > 0.0:
                # Pre-computed log(2) = 0.6931471805599453
                decay_const = 0.6931471805599453 / halflife
                decay_factor = math.exp(-decay_const * idle_time)
                decayed_odds[pid] = log_odd * decay_factor
            else:
                decayed_odds[pid] = log_odd

        # Convert log-odds to probabilities using softmax
        max_odd = max(decayed_odds.values()) if decayed_odds else 0.0
        exp_odds = {}

        for pid, log_odd in decayed_odds.items():
            # Subtract max for numerical stability (softmax trick)
            exp_odds[pid] = math.exp(log_odd - max_odd)

        total = sum(exp_odds.values())
        if total == 0:
            # Uniform distribution
            n = len(exp_odds)
            return {pid: 1.0 / n for pid in exp_odds}

        return {pid: exp_val / total for pid, exp_val in exp_odds.items()}

    def get_top_candidate(self) -> Optional[tuple[str, float]]:
        """Return the participant with highest probability."""
        probs = self.get_probabilities()
        if not probs:
            return None
        top_pid = max(probs, key=probs.get)
        return (top_pid, probs[top_pid])

    def get_evidence_summary(self, participant_id: str) -> list[EvidenceItem]:
        """Get all evidence for a specific participant, sorted by impact."""
        items = [e for e in self._evidence_history if e.participant_id == participant_id]
        items.sort(key=lambda e: abs(e.score * e.weight * e.confidence), reverse=True)
        return items

    def reset(self) -> None:
        """Reset the engine for a new meeting."""
        self._log_odds.clear()
        self._evidence_history.clear()
        self._current_time = 0.0
