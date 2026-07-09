"""Calendar Match Analyzer — matches participants against calendar invite metadata.

Signals:
- Participant name/email matches candidate in calendar
- Participant matches known interviewer
- Number of participants vs expected attendees
"""

from __future__ import annotations

from typing import Optional

from backend.app.core.analyzers.base import BaseAnalyzer
from backend.app.core.analyzers.name_similarity import _levenshtein_ratio, _normalize, _token_overlap
from backend.app.models.events import CalendarMetadata, EventType, MeetingEvent
from backend.app.models.evidence import EvidenceItem, SignalType
from backend.app.models.participant import ParticipantState


class CalendarMatchAnalyzer(BaseAnalyzer):
    """Matches participants against calendar invite attendees."""

    def __init__(self, weight: float = 20.0):
        super().__init__(weight)
        self._matched_participants: set[str] = set()

    def get_signal_type(self) -> str:
        return SignalType.CALENDAR_MATCH

    def analyze(
        self,
        event: MeetingEvent,
        participants: dict[str, ParticipantState],
        calendar: Optional[CalendarMetadata] = None,
        transcript_history: Optional[list] = None,
    ) -> list[EvidenceItem]:
        evidence = []

        if not calendar:
            return evidence

        if event.event_type != EventType.PARTICIPANT_JOINED:
            return evidence

        pid = event.participant_id
        if not pid or pid not in participants:
            return evidence

        if pid in self._matched_participants:
            return evidence

        self._matched_participants.add(pid)
        participant = participants[pid]
        display_name = participant.display_name
        norm_display = _normalize(display_name)

        # Check candidate match
        candidate_name = calendar.candidate_name
        candidate_email = calendar.candidate_email or ""
        norm_candidate = _normalize(candidate_name)

        # Direct name match
        name_sim = max(
            _token_overlap(display_name, candidate_name),
            _levenshtein_ratio(norm_display, norm_candidate)
        )

        # Email match
        email_sim = 0.0
        if candidate_email:
            email_prefix = candidate_email.split("@")[0].replace(".", " ").replace("_", " ")
            email_data = event.data.get("email", "")
            if email_data and email_data.lower() == candidate_email.lower():
                email_sim = 1.0
            else:
                email_sim = _token_overlap(display_name, email_prefix)

        best_candidate_sim = max(name_sim, email_sim)

        if best_candidate_sim > 0.5:
            evidence.append(EvidenceItem(
                signal_type=SignalType.CALENDAR_MATCH,
                participant_id=pid,
                score=best_candidate_sim,
                weight=self.weight,
                confidence=best_candidate_sim,
                reason=f"'{display_name}' matches calendar candidate '{candidate_name}' (confidence: {best_candidate_sim:.0%})",
                timestamp=event.timestamp,
                details={"name_sim": name_sim, "email_sim": email_sim, "match": "candidate"},
            ))

        # Check interviewer match
        interviewer_names = calendar.interviewer_names or []
        for int_name in interviewer_names:
            int_sim = max(
                _token_overlap(display_name, int_name),
                _levenshtein_ratio(norm_display, _normalize(int_name))
            )
            if int_sim > 0.5:
                evidence.append(EvidenceItem(
                    signal_type=SignalType.CALENDAR_MATCH,
                    participant_id=pid,
                    score=-int_sim,  # Negative: identified as interviewer
                    weight=self.weight,
                    confidence=int_sim,
                    reason=f"'{display_name}' matches calendar interviewer '{int_name}' — NOT the candidate",
                    timestamp=event.timestamp,
                    details={"interviewer": int_name, "similarity": int_sim, "match": "interviewer"},
                ))
                break

        # If neither candidate nor interviewer match
        if not evidence:
            # Unknown participant — slight positive if we have few participants
            num_participants = len(participants)
            num_expected = 1 + len(interviewer_names)  # candidate + interviewers

            if num_participants <= num_expected:
                # This unknown person might be the candidate
                evidence.append(EvidenceItem(
                    signal_type=SignalType.CALENDAR_MATCH,
                    participant_id=pid,
                    score=0.1,
                    weight=self.weight * 0.3,
                    confidence=0.3,
                    reason=f"'{display_name}' is unrecognized — could be candidate with different display name",
                    timestamp=event.timestamp,
                    details={"match": "unknown", "num_participants": num_participants},
                ))
            else:
                # Extra participant — likely observer
                evidence.append(EvidenceItem(
                    signal_type=SignalType.CALENDAR_MATCH,
                    participant_id=pid,
                    score=-0.2,
                    weight=self.weight * 0.3,
                    confidence=0.4,
                    reason=f"'{display_name}' is an extra participant beyond expected — likely observer",
                    timestamp=event.timestamp,
                    details={"match": "extra", "num_participants": num_participants},
                ))

        return evidence

    def reset(self) -> None:
        self._matched_participants.clear()
