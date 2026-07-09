"""Unit tests for signal analyzers."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.core.analyzers.name_similarity import (
    NameSimilarityAnalyzer,
    _levenshtein_ratio,
    _token_overlap,
    _is_device_name,
)
from backend.app.core.analyzers.calendar_match import CalendarMatchAnalyzer
from backend.app.core.analyzers.speech_pattern import SpeechPatternAnalyzer
from backend.app.core.analyzers.transcript import TranscriptAnalyzer
from backend.app.core.analyzers.behavioral import BehavioralAnalyzer
from backend.app.core.analyzers.temporal import TemporalAnalyzer
from backend.app.models.events import CalendarMetadata, EventType, MeetingEvent
from backend.app.models.participant import ParticipantState


def test_levenshtein_ratio():
    assert _levenshtein_ratio("hello", "hello") == 1.0
    assert _levenshtein_ratio("", "") == 0.0
    assert _levenshtein_ratio("hello", "helo") > 0.7
    assert _levenshtein_ratio("abc", "xyz") < 0.5
    print("  [PASS] Levenshtein ratio")


def test_token_overlap():
    assert _token_overlap("Priya Sharma", "Priya Sharma") == 1.0
    assert _token_overlap("Priya S", "Priya Sharma") == 0.5
    assert _token_overlap("John", "Jane") == 0.0
    assert _token_overlap("Alex Chen", "Alex") > 0
    print("  [PASS] Token overlap")


def test_device_name_detection():
    assert _is_device_name("MacBook Pro") == True
    assert _is_device_name("iPhone") == True
    assert _is_device_name("Priya Sharma") == False
    assert _is_device_name("Alex Chen") == False
    assert _is_device_name("Samsung Galaxy") == True
    print("  [PASS] Device name detection")


def test_name_similarity_analyzer():
    analyzer = NameSimilarityAnalyzer()
    calendar = CalendarMetadata(
        candidate_name="Priya Sharma",
        candidate_email="priya.sharma@gmail.com",
        interviewer_names=["Alex Chen"],
    )
    participants = {
        "p1": ParticipantState(participant_id="p1", display_name="Alex Chen"),
        "p2": ParticipantState(participant_id="p2", display_name="Priya Sharma"),
    }

    # Test candidate match
    event = MeetingEvent(event_type=EventType.PARTICIPANT_JOINED, participant_id="p2", timestamp=10)
    evidence = analyzer.analyze(event, participants, calendar)
    assert len(evidence) > 0
    assert any(e.score > 0.5 for e in evidence), "Should find strong name match"

    # Test interviewer match
    event2 = MeetingEvent(event_type=EventType.PARTICIPANT_JOINED, participant_id="p1", timestamp=5)
    evidence2 = analyzer.analyze(event2, participants, calendar)
    assert any(e.score < 0 for e in evidence2), "Should detect interviewer"
    print("  [PASS] Name similarity analyzer")


def test_transcript_analyzer():
    analyzer = TranscriptAnalyzer()
    calendar = CalendarMetadata(candidate_name="Priya Sharma", interviewer_names=["Alex"])
    participants = {
        "p1": ParticipantState(participant_id="p1", display_name="Alex Chen"),
        "p2": ParticipantState(participant_id="p2", display_name="Priya"),
    }

    # Self introduction
    event = MeetingEvent(
        event_type=EventType.TRANSCRIPT_CHUNK,
        participant_id="p2",
        timestamp=30,
        data={"text": "Hi, I'm Priya Sharma, I applied for the engineering position."},
    )
    evidence = analyzer.analyze(event, participants, calendar)
    assert any(e.score > 0 for e in evidence), "Should detect self-introduction"

    # Interviewer pattern
    event2 = MeetingEvent(
        event_type=EventType.TRANSCRIPT_CHUNK,
        participant_id="p1",
        timestamp=20,
        data={"text": "Welcome! Can you tell me about yourself and your background?"},
    )
    evidence2 = analyzer.analyze(event2, participants, calendar)
    assert any(e.score < 0 for e in evidence2), "Should detect interviewer pattern"
    print("  [PASS] Transcript analyzer")


def test_behavioral_analyzer():
    analyzer = BehavioralAnalyzer()
    participants = {
        "p1": ParticipantState(participant_id="p1", display_name="Alex"),
    }

    # Screen share = interviewer signal
    event = MeetingEvent(
        event_type=EventType.SCREEN_SHARE_STARTED,
        participant_id="p1",
        timestamp=50,
    )
    evidence = analyzer.analyze(event, participants)
    assert any(e.score < 0 for e in evidence), "Screen share should be negative evidence"
    print("  [PASS] Behavioral analyzer")


def test_temporal_analyzer():
    analyzer = TemporalAnalyzer()
    participants = {
        "p1": ParticipantState(participant_id="p1", display_name="Alex", join_time=0),
        "p2": ParticipantState(participant_id="p2", display_name="Priya", join_time=15),
    }

    # First joiner
    event1 = MeetingEvent(event_type=EventType.PARTICIPANT_JOINED, participant_id="p1", timestamp=0)
    analyzer.analyze(event1, participants)

    # Second joiner triggers analysis
    event2 = MeetingEvent(event_type=EventType.PARTICIPANT_JOINED, participant_id="p2", timestamp=15)
    evidence = analyzer.analyze(event2, participants)
    assert len(evidence) > 0, "Should produce join order evidence"
    print("  [PASS] Temporal analyzer")


if __name__ == "__main__":
    print("\n  Running analyzer tests...\n")
    test_levenshtein_ratio()
    test_token_overlap()
    test_device_name_detection()
    test_name_similarity_analyzer()
    test_transcript_analyzer()
    test_behavioral_analyzer()
    test_temporal_analyzer()
    print("\n  All tests passed! [PASS]\n")
