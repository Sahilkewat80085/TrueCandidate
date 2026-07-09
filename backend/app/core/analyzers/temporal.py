"""Temporal Analyzer — analyzes timing patterns and interaction dynamics.

Key temporal signals:
- Join order: Interviewer usually joins first, candidate second
- Response timing: Who responds to whom
- Turn-taking patterns: Interview has structured turn-taking
- Activity timeline: When each participant becomes active
"""

from __future__ import annotations

from typing import Optional

from backend.app.core.analyzers.base import BaseAnalyzer
from backend.app.models.events import CalendarMetadata, EventType, MeetingEvent
from backend.app.models.evidence import EvidenceItem, SignalType
from backend.app.models.participant import ParticipantState


class TemporalAnalyzer(BaseAnalyzer):
    """Analyzes temporal patterns and interaction dynamics."""

    def __init__(self, weight: float = 5.0):
        super().__init__(weight)
        self._join_order: list[str] = []
        self._speaking_sequence: list[str] = []
        self._last_speaker: Optional[str] = None
        self._turn_counts: dict[str, int] = {}
        self._response_map: dict[str, dict[str, int]] = {}  # who responds to whom
        self._analyzed_join = False

    def get_signal_type(self) -> str:
        return SignalType.TEMPORAL

    def analyze(
        self,
        event: MeetingEvent,
        participants: dict[str, ParticipantState],
        calendar: Optional[CalendarMetadata] = None,
        transcript_history: Optional[list] = None,
    ) -> list[EvidenceItem]:
        evidence = []
        pid = event.participant_id

        # Track join order
        if event.event_type == EventType.PARTICIPANT_JOINED and pid:
            if pid not in self._join_order:
                self._join_order.append(pid)

        # Track speaking sequence for turn-taking analysis
        if event.event_type == EventType.SPEAKING_STARTED and pid:
            if self._last_speaker and self._last_speaker != pid:
                # Record who responds to whom
                if pid not in self._response_map:
                    self._response_map[pid] = {}
                self._response_map[pid][self._last_speaker] = \
                    self._response_map[pid].get(self._last_speaker, 0) + 1

            self._last_speaker = pid
            self._turn_counts[pid] = self._turn_counts.get(pid, 0) + 1

        # Analyze join order once we have enough participants
        if (event.event_type == EventType.PARTICIPANT_JOINED
            and len(self._join_order) >= 2
            and not self._analyzed_join):
            self._analyzed_join = True

            for idx, p_id in enumerate(self._join_order):
                if p_id not in participants:
                    continue
                p = participants[p_id]

                if idx == 0:
                    # First to join — likely interviewer (they set up the call)
                    evidence.append(EvidenceItem(
                        signal_type=SignalType.TEMPORAL,
                        participant_id=p_id,
                        score=-0.3,
                        weight=self.weight,
                        confidence=0.5,
                        reason=f"'{p.display_name}' joined first — typically interviewer sets up the call",
                        timestamp=event.timestamp,
                        details={"join_order": idx + 1},
                    ))
                elif idx == 1 and len(self._join_order) == 2:
                    # Second to join in a 2-person meeting — likely candidate
                    evidence.append(EvidenceItem(
                        signal_type=SignalType.TEMPORAL,
                        participant_id=p_id,
                        score=0.2,
                        weight=self.weight,
                        confidence=0.4,
                        reason=f"'{p.display_name}' joined second — candidates typically join after interviewer",
                        timestamp=event.timestamp,
                        details={"join_order": idx + 1},
                    ))

            # Late joiners (joined much later)
            if len(self._join_order) >= 3:
                first_join = participants[self._join_order[0]].join_time if self._join_order[0] in participants else 0
                for p_id in self._join_order[2:]:
                    if p_id in participants:
                        p = participants[p_id]
                        delay = p.join_time - first_join
                        if delay > 60:  # More than 1 minute late
                            evidence.append(EvidenceItem(
                                signal_type=SignalType.TEMPORAL,
                                participant_id=p_id,
                                score=-0.2,
                                weight=self.weight * 0.5,
                                confidence=0.4,
                                reason=f"'{p.display_name}' joined {delay:.0f}s after meeting started — likely observer joining late",
                                timestamp=event.timestamp,
                                details={"delay": delay, "join_order": self._join_order.index(p_id) + 1},
                            ))

        # Periodic turn-taking analysis
        if event.event_type == EventType.SPEAKING_STOPPED and len(self._turn_counts) >= 2:
            total_turns = sum(self._turn_counts.values())
            if total_turns >= 6:  # Need enough data
                for p_id, turns in self._turn_counts.items():
                    if p_id not in participants:
                        continue
                    p = participants[p_id]
                    turn_ratio = turns / total_turns

                    # In interviews, candidate and interviewer alternate
                    # Both should have roughly equal turns, but candidate turns are longer
                    if 0.3 <= turn_ratio <= 0.55:
                        # Healthy turn-taking — could be candidate or interviewer
                        # Check if this person has LONGER turns (candidate pattern)
                        avg_duration = p.total_speaking_duration / max(turns, 1)
                        if avg_duration > 8:  # Long turns = more likely candidate
                            evidence.append(EvidenceItem(
                                signal_type=SignalType.TEMPORAL,
                                participant_id=p_id,
                                score=0.3,
                                weight=self.weight * 0.7,
                                confidence=0.5,
                                reason=f"'{p.display_name}' has balanced turn-taking ({turn_ratio:.0%}) with long segments ({avg_duration:.0f}s avg) — candidate pattern",
                                timestamp=event.timestamp,
                                details={"turns": turns, "turn_ratio": turn_ratio, "avg_duration": avg_duration},
                            ))

        return evidence

    def reset(self) -> None:
        self._join_order.clear()
        self._speaking_sequence.clear()
        self._last_speaker = None
        self._turn_counts.clear()
        self._response_map.clear()
        self._analyzed_join = False
