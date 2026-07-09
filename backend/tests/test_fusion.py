"""Tests for the fusion and confidence engines."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.config import AppConfig
from backend.app.fusion.fusion_engine import FusionEngine
from backend.app.confidence.confidence_engine import ConfidenceEngine
from backend.app.models.evidence import EvidenceItem, SignalType


def test_fusion_engine_basic():
    engine = FusionEngine()
    engine.add_participant("p1")
    engine.add_participant("p2")

    # Add positive evidence for p1
    evidence = EvidenceItem(
        signal_type=SignalType.NAME_SIMILARITY,
        participant_id="p1",
        score=0.9,
        weight=15.0,
        confidence=0.95,
        reason="Name matches candidate",
        timestamp=10.0,
    )
    probs = engine.update(evidence)

    assert probs["p1"] > probs["p2"], "p1 should have higher probability after positive evidence"
    assert abs(sum(probs.values()) - 1.0) < 0.01, "Probabilities should sum to 1"
    print("  [PASS] Fusion engine basic")


def test_fusion_engine_competing_evidence():
    engine = FusionEngine()
    engine.add_participant("p1")
    engine.add_participant("p2")

    # Positive for p1
    engine.update(EvidenceItem(
        signal_type=SignalType.NAME_SIMILARITY, participant_id="p1",
        score=0.9, weight=15.0, confidence=0.95, reason="Name match", timestamp=10,
    ))

    # Negative for p1 (found to be interviewer)
    engine.update(EvidenceItem(
        signal_type=SignalType.TRANSCRIPT_EVIDENCE, participant_id="p1",
        score=-0.7, weight=25.0, confidence=0.8, reason="Asks questions", timestamp=30,
    ))

    # Positive for p2
    engine.update(EvidenceItem(
        signal_type=SignalType.SPEECH_PATTERN, participant_id="p2",
        score=0.8, weight=10.0, confidence=0.7, reason="High speaking", timestamp=40,
    ))

    probs = engine.get_probabilities()
    # After competing evidence, relative ordering may change
    assert len(probs) == 2
    assert abs(sum(probs.values()) - 1.0) < 0.01
    print("  [PASS] Fusion engine competing evidence")


def test_fusion_engine_top_candidate():
    engine = FusionEngine()
    engine.add_participant("p1")
    engine.add_participant("p2")
    engine.add_participant("p3")

    engine.update(EvidenceItem(
        signal_type=SignalType.CALENDAR_MATCH, participant_id="p2",
        score=0.95, weight=20.0, confidence=0.95, reason="Calendar match", timestamp=5,
    ))

    top = engine.get_top_candidate()
    assert top is not None
    assert top[0] == "p2", "p2 should be top candidate"
    print("  [PASS] Fusion engine top candidate")


def test_confidence_engine():
    engine = ConfidenceEngine()

    # Simulate rising confidence
    for i in range(10):
        probs = {"p1": 0.3 + i * 0.06, "p2": 0.7 - i * 0.06}
        engine.update(probs, timestamp=i * 10)

    conf_p1 = engine.get_confidence("p1")
    conf_p2 = engine.get_confidence("p2")

    # After smoothing, p1 should be rising
    assert conf_p1 > 0.3, f"p1 confidence should be rising, got {conf_p1}"

    # Timeline should have entries
    timeline = engine.get_timeline()
    assert len(timeline) > 0

    # Trend
    trend_p1 = engine.get_trend("p1")
    assert trend_p1 == "rising", f"p1 should be rising, got {trend_p1}"
    print("  [PASS] Confidence engine")


def test_confidence_levels():
    engine = ConfidenceEngine()
    engine.update({"p1": 0.95}, timestamp=1)
    assert engine.get_confidence_level("p1") == "very_high"

    engine2 = ConfidenceEngine()
    engine2.update({"p1": 0.2}, timestamp=1)
    assert engine2.get_confidence_level("p1") == "low"
    print("  [PASS] Confidence levels")


if __name__ == "__main__":
    print("\n  Running fusion & confidence tests...\n")
    test_fusion_engine_basic()
    test_fusion_engine_competing_evidence()
    test_fusion_engine_top_candidate()
    test_confidence_engine()
    test_confidence_levels()
    print("\n  All tests passed! [PASS]\n")
