"""Speech Pattern Analyzer — analyzes speaking behavior to identify the candidate.

In a typical interview:
- Candidate speaks the MOST (answering questions)
- Candidate has LONGER speaking segments (explaining experiences)
- Interviewer speaks in shorter segments (asking questions)
- Observers are SILENT or speak very little
"""

from __future__ import annotations

from typing import Optional

from backend.app.core.analyzers.base import BaseAnalyzer
from backend.app.models.events import CalendarMetadata, EventType, MeetingEvent
from backend.app.models.evidence import EvidenceItem, SignalType
from backend.app.models.participant import ParticipantState


class SpeechPatternAnalyzer(BaseAnalyzer):
    """Analyzes speaking patterns to identify candidate vs interviewer vs observer."""

    def __init__(self, weight: float = 10.0):
        super().__init__(weight)
        self._last_analysis_time: float = 0.0
        self._analysis_interval: float = 10.0  # Analyze every 10 seconds
        self._speaking_starts: dict[str, float] = {}

    def get_signal_type(self) -> str:
        return SignalType.SPEECH_PATTERN

    def analyze(
        self,
        event: MeetingEvent,
        participants: dict[str, ParticipantState],
        calendar: Optional[CalendarMetadata] = None,
        transcript_history: Optional[list] = None,
    ) -> list[EvidenceItem]:
        evidence = []
        pid = event.participant_id

        # Track speaking start/stop for accurate duration
        if event.event_type == EventType.SPEAKING_STARTED and pid:
            self._speaking_starts[pid] = event.timestamp
            return evidence

        if event.event_type == EventType.SPEAKING_STOPPED and pid:
            start = self._speaking_starts.pop(pid, None)
            if start is not None and pid in participants:
                duration = event.timestamp - start
                participants[pid].total_speaking_duration += duration
                participants[pid].speaking_segments += 1

        # Periodic analysis — don't analyze on every event
        if event.timestamp - self._last_analysis_time < self._analysis_interval:
            return evidence

        self._last_analysis_time = event.timestamp

        # Need at least 2 participants who have spoken
        speaking_participants = {
            pid: p for pid, p in participants.items()
            if p.total_speaking_duration > 0 and p.is_active
        }

        if len(speaking_participants) < 2:
            return evidence

        # Calculate speaking stats
        total_duration = sum(p.total_speaking_duration for p in speaking_participants.values())
        if total_duration == 0:
            return evidence

        for pid, participant in speaking_participants.items():
            speech_ratio = participant.total_speaking_duration / total_duration
            avg_segment_duration = (
                participant.total_speaking_duration / participant.speaking_segments
                if participant.speaking_segments > 0 else 0
            )

            # Candidate typically speaks 40-70% of the time in an interview
            # and has longer average segment durations
            if speech_ratio > 0.35:
                # High speaking ratio — likely candidate
                score = min(speech_ratio * 1.2, 1.0)
                evidence.append(EvidenceItem(
                    signal_type=SignalType.SPEECH_PATTERN,
                    participant_id=pid,
                    score=score,
                    weight=self.weight,
                    confidence=min(speech_ratio + 0.2, 0.9),
                    reason=f"'{participant.display_name}' has {speech_ratio:.0%} of speaking time ({participant.total_speaking_duration:.0f}s) — consistent with candidate",
                    timestamp=event.timestamp,
                    details={
                        "speech_ratio": speech_ratio,
                        "total_duration": participant.total_speaking_duration,
                        "segments": participant.speaking_segments,
                        "avg_segment": avg_segment_duration,
                    },
                ))
            elif speech_ratio > 0.15:
                # Moderate speaking — could be interviewer
                score = -0.2  # Slight negative
                evidence.append(EvidenceItem(
                    signal_type=SignalType.SPEECH_PATTERN,
                    participant_id=pid,
                    score=score,
                    weight=self.weight * 0.5,
                    confidence=0.4,
                    reason=f"'{participant.display_name}' has moderate speaking time ({speech_ratio:.0%}) — consistent with interviewer",
                    timestamp=event.timestamp,
                    details={"speech_ratio": speech_ratio},
                ))
            else:
                # Very little speaking — likely observer
                evidence.append(EvidenceItem(
                    signal_type=SignalType.SPEECH_PATTERN,
                    participant_id=pid,
                    score=-0.5,
                    weight=self.weight * 0.6,
                    confidence=0.6,
                    reason=f"'{participant.display_name}' barely speaks ({speech_ratio:.0%}) — likely observer",
                    timestamp=event.timestamp,
                    details={"speech_ratio": speech_ratio},
                ))

        # Silent participants get negative evidence
        for pid, participant in participants.items():
            if pid not in speaking_participants and participant.is_active:
                if event.timestamp - participant.join_time > 30:  # Give 30s grace period
                    evidence.append(EvidenceItem(
                        signal_type=SignalType.SPEECH_PATTERN,
                        participant_id=pid,
                        score=-0.6,
                        weight=self.weight * 0.7,
                        confidence=0.7,
                        reason=f"'{participant.display_name}' has not spoken at all — likely observer",
                        timestamp=event.timestamp,
                        details={"silent_duration": event.timestamp - participant.join_time},
                    ))

        return evidence

    def reset(self) -> None:
        self._last_analysis_time = 0.0
        self._speaking_starts.clear()
