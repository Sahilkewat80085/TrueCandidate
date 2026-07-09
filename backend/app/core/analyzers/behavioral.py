"""Behavioral Analyzer — analyzes webcam, mic, and screen share patterns.

Key behavioral signals:
- Candidates typically keep webcam ON (they need to be seen)
- Interviewers may screen-share (presenting problems)
- Observers often have webcam OFF
- Frequent join/leave is suspicious
- Camera toggling patterns differ between roles
"""

from __future__ import annotations

from typing import Optional

from backend.app.core.analyzers.base import BaseAnalyzer
from backend.app.models.events import CalendarMetadata, EventType, MeetingEvent
from backend.app.models.evidence import EvidenceItem, SignalType
from backend.app.models.participant import ParticipantState


class BehavioralAnalyzer(BaseAnalyzer):
    """Analyzes behavioral patterns (webcam, screen share, join/leave)."""

    def __init__(self, weight: float = 10.0):
        super().__init__(weight)
        self._webcam_starts: dict[str, float] = {}
        self._rejoin_counts: dict[str, int] = {}
        self._screen_sharers: set[str] = set()
        self._last_analysis_time: float = 0.0
        self._analysis_interval: float = 15.0

    def get_signal_type(self) -> str:
        return SignalType.BEHAVIORAL

    def analyze(
        self,
        event: MeetingEvent,
        participants: dict[str, ParticipantState],
        calendar: Optional[CalendarMetadata] = None,
        transcript_history: Optional[list] = None,
    ) -> list[EvidenceItem]:
        evidence = []
        pid = event.participant_id

        if not pid or pid not in participants:
            return evidence

        participant = participants[pid]

        # Track webcam on/off
        if event.event_type == EventType.WEBCAM_ENABLED:
            participant.webcam_on = True
            self._webcam_starts[pid] = event.timestamp

        elif event.event_type == EventType.WEBCAM_DISABLED:
            participant.webcam_on = False
            start = self._webcam_starts.pop(pid, None)
            if start is not None:
                participant.webcam_on_duration += event.timestamp - start

        # Screen share — strong interviewer signal
        elif event.event_type == EventType.SCREEN_SHARE_STARTED:
            participant.is_screen_sharing = True
            self._screen_sharers.add(pid)
            evidence.append(EvidenceItem(
                signal_type=SignalType.BEHAVIORAL,
                participant_id=pid,
                score=-0.7,
                weight=self.weight,
                confidence=0.8,
                reason=f"'{participant.display_name}' started screen sharing — typically interviewer behavior",
                timestamp=event.timestamp,
                details={"behavior": "screen_share"},
            ))

        elif event.event_type == EventType.SCREEN_SHARE_STOPPED:
            participant.is_screen_sharing = False

        # Rejoin detection
        elif event.event_type == EventType.PARTICIPANT_JOINED:
            self._rejoin_counts[pid] = self._rejoin_counts.get(pid, 0) + 1
            if self._rejoin_counts[pid] > 1:
                evidence.append(EvidenceItem(
                    signal_type=SignalType.PENALTY,
                    participant_id=pid,
                    score=-0.3,
                    weight=3.0,
                    confidence=0.7,
                    reason=f"'{participant.display_name}' rejoined the meeting (count: {self._rejoin_counts[pid]}) — connection instability",
                    timestamp=event.timestamp,
                    details={"rejoin_count": self._rejoin_counts[pid]},
                ))

        # Display name change — penalty signal
        elif event.event_type == EventType.DISPLAY_NAME_CHANGED:
            old_name = event.data.get("old_name", "")
            new_name = event.data.get("new_name", participant.display_name)
            participant.display_name = new_name
            participant.display_name_history.append(old_name)

            evidence.append(EvidenceItem(
                signal_type=SignalType.PENALTY,
                participant_id=pid,
                score=-0.2,
                weight=5.0,
                confidence=0.6,
                reason=f"'{old_name}' changed display name to '{new_name}'",
                timestamp=event.timestamp,
                details={"old_name": old_name, "new_name": new_name},
            ))

            # But if name changed TO match candidate, that's positive evidence
            if calendar:
                from backend.app.core.analyzers.name_similarity import _token_overlap
                sim = _token_overlap(new_name, calendar.candidate_name)
                if sim > 0.3:
                    evidence.append(EvidenceItem(
                        signal_type=SignalType.BEHAVIORAL,
                        participant_id=pid,
                        score=0.6,
                        weight=self.weight,
                        confidence=sim,
                        reason=f"Display name changed to '{new_name}' which matches candidate '{calendar.candidate_name}'",
                        timestamp=event.timestamp,
                        details={"new_name": new_name, "similarity": sim},
                    ))

        # Periodic webcam analysis
        if event.timestamp - self._last_analysis_time >= self._analysis_interval:
            self._last_analysis_time = event.timestamp

            for p_id, p in participants.items():
                if not p.is_active:
                    continue

                # Update webcam duration for currently-on cameras
                if p.webcam_on and p_id in self._webcam_starts:
                    current_duration = p.webcam_on_duration + (event.timestamp - self._webcam_starts[p_id])
                else:
                    current_duration = p.webcam_on_duration

                time_in_meeting = max(event.timestamp - p.join_time, 1)
                webcam_ratio = current_duration / time_in_meeting

                if webcam_ratio > 0.8 and time_in_meeting > 20:
                    evidence.append(EvidenceItem(
                        signal_type=SignalType.BEHAVIORAL,
                        participant_id=p_id,
                        score=0.3,
                        weight=self.weight * 0.6,
                        confidence=min(webcam_ratio, 0.8),
                        reason=f"'{p.display_name}' webcam on {webcam_ratio:.0%} of meeting — consistent with candidate",
                        timestamp=event.timestamp,
                        details={"webcam_ratio": webcam_ratio, "webcam_duration": current_duration},
                    ))
                elif webcam_ratio < 0.1 and time_in_meeting > 30:
                    evidence.append(EvidenceItem(
                        signal_type=SignalType.BEHAVIORAL,
                        participant_id=p_id,
                        score=-0.4,
                        weight=self.weight * 0.5,
                        confidence=0.6,
                        reason=f"'{p.display_name}' webcam off most of meeting ({webcam_ratio:.0%}) — likely observer",
                        timestamp=event.timestamp,
                        details={"webcam_ratio": webcam_ratio},
                    ))

        return evidence

    def reset(self) -> None:
        self._webcam_starts.clear()
        self._rejoin_counts.clear()
        self._screen_sharers.clear()
        self._last_analysis_time = 0.0
