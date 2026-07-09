"""Explainability Engine — generates human-readable explanations for predictions.

Every prediction must be explainable:
- WHY was this participant selected?
- WHAT evidence supports/contradicts the selection?
- WHERE is there uncertainty?
- HOW confident is the system and why?
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.app.confidence.confidence_engine import ConfidenceEngine
from backend.app.fusion.fusion_engine import FusionEngine
from backend.app.models.evidence import EvidenceItem
from backend.app.models.participant import ParticipantState
from backend.app.models.prediction import (
    CandidatePrediction,
    ParticipantPrediction,
    ReasonItem,
)

logger = logging.getLogger(__name__)


class ExplainabilityEngine:
    """Generates human-readable explanations for candidate predictions."""

    def __init__(
        self,
        fusion_engine: FusionEngine,
        confidence_engine: ConfidenceEngine,
    ):
        self.fusion = fusion_engine
        self.confidence = confidence_engine

    def generate_prediction(
        self,
        meeting_id: str,
        participants: dict[str, ParticipantState],
        timestamp: float = 0.0,
    ) -> CandidatePrediction:
        """Generate a full prediction with explanation.
        
        Returns a CandidatePrediction with:
        - Current candidate and confidence
        - Top reasons (positive and negative)
        - All participant predictions
        - Uncertainty factors
        """
        confidences = self.confidence.get_all_confidences()
        top = self.confidence.get_top_candidate()

        if not top or not confidences:
            return CandidatePrediction(
                meeting_id=meeting_id,
                confidence=0.0,
                confidence_level="low",
                uncertainty_factors=["No participants or evidence available yet"],
                timestamp=timestamp,
            )

        top_pid, top_conf = top
        top_participant = participants.get(top_pid)

        # Build reasons for the top candidate
        top_reasons = self._build_reasons(top_pid)

        # Build all participant predictions
        all_preds = []
        for pid, p in participants.items():
            if not p.is_active:
                continue
            conf = confidences.get(pid, 0.0)
            role = self._infer_role(pid, conf, participants)
            reasons = self._build_reasons(pid, max_reasons=3)

            all_preds.append(ParticipantPrediction(
                participant_id=pid,
                display_name=p.display_name,
                confidence=round(conf, 4),
                role=role,
                top_reasons=reasons,
            ))

        # Sort by confidence descending
        all_preds.sort(key=lambda p: p.confidence, reverse=True)

        # Build uncertainty factors
        uncertainty = self._identify_uncertainties(top_pid, top_conf, participants, confidences)

        # Confidence level
        conf_level = self.confidence.get_confidence_level(top_pid)

        return CandidatePrediction(
            meeting_id=meeting_id,
            current_candidate_id=top_pid,
            current_candidate_name=top_participant.display_name if top_participant else None,
            confidence=round(top_conf, 4),
            confidence_level=conf_level,
            top_reasons=top_reasons,
            all_participants=all_preds,
            uncertainty_factors=uncertainty,
            timestamp=timestamp,
        )

    def _build_reasons(self, participant_id: str, max_reasons: int = 6) -> list[ReasonItem]:
        """Build ranked list of reasons for a participant's score."""
        evidence = self.fusion.get_evidence_summary(participant_id)
        reasons = []

        # Group by signal type and take the most impactful
        seen_types = set()
        for item in evidence[:max_reasons * 2]:  # Check more than needed
            if len(reasons) >= max_reasons:
                break

            # Deduplicate by signal type (keep most impactful)
            key = (item.signal_type, "pos" if item.score > 0 else "neg")
            if key in seen_types:
                continue
            seen_types.add(key)

            impact_value = item.score * item.weight * item.confidence
            impact_str = f"+{abs(impact_value):.0f}" if impact_value > 0 else f"-{abs(impact_value):.0f}"

            if item.score > 0:
                icon = "positive"
            elif item.score < 0:
                icon = "negative"
            else:
                icon = "info"

            reasons.append(ReasonItem(
                signal=item.signal_type,
                impact=impact_str,
                reason=item.reason,
                icon=icon,
            ))

        return reasons

    def _infer_role(
        self,
        participant_id: str,
        confidence: float,
        participants: dict[str, ParticipantState],
    ) -> str:
        """Infer the role of a participant based on evidence patterns."""
        evidence = self.fusion.get_evidence_summary(participant_id)

        if confidence > 0.5:
            return "candidate"

        # Check for interviewer signals
        negative_signals = sum(1 for e in evidence if e.score < -0.3)
        positive_signals = sum(1 for e in evidence if e.score > 0.3)

        if negative_signals > positive_signals:
            # Check if participant has been speaking (interviewer vs observer)
            p = participants.get(participant_id)
            if p and p.total_speaking_duration > 10:
                return "interviewer"
            return "observer"

        return "unknown"

    def _identify_uncertainties(
        self,
        top_pid: str,
        top_conf: float,
        participants: dict[str, ParticipantState],
        confidences: dict[str, float],
    ) -> list[str]:
        """Identify factors that create uncertainty in the prediction."""
        factors = []

        # Low overall confidence
        if top_conf < 0.5:
            factors.append("Overall confidence is low — not enough evidence to make a strong prediction")

        # Close second candidate
        sorted_confs = sorted(confidences.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_confs) >= 2:
            gap = sorted_confs[0][1] - sorted_confs[1][1]
            if gap < 0.15:
                second_pid = sorted_confs[1][0]
                second_name = participants.get(second_pid, ParticipantState(
                    participant_id=second_pid, display_name="Unknown"
                )).display_name
                factors.append(
                    f"Second candidate '{second_name}' has similar confidence "
                    f"({sorted_confs[1][1]:.0%} vs {sorted_confs[0][1]:.0%}) — ambiguous"
                )

        # Check for contradictory evidence
        top_evidence = self.fusion.get_evidence_summary(top_pid)
        neg_count = sum(1 for e in top_evidence if e.score < 0)
        if neg_count >= 2:
            factors.append(f"Top candidate has {neg_count} pieces of contradictory evidence")

        # Confidence trend
        trend = self.confidence.get_trend(top_pid)
        if trend == "falling":
            factors.append("Confidence is currently declining — recent counter-evidence received")

        # Stability
        stability = self.confidence.get_stability(top_pid)
        if stability < 0.5:
            factors.append("Confidence has been unstable — prediction may change")

        # Display name mismatch
        top_participant = participants.get(top_pid)
        if top_participant:
            from backend.app.core.analyzers.name_similarity import _is_device_name
            if _is_device_name(top_participant.display_name):
                factors.append(
                    f"Display name '{top_participant.display_name}' is a device name — "
                    "identification relies on behavioral signals only"
                )

        return factors
