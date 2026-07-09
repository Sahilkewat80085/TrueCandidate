"""Name Similarity Analyzer — fuzzy matches display names against candidate info.

Uses multiple string similarity algorithms:
- Exact match
- Case-insensitive match
- Token overlap (handles "Priya S" vs "Priya Sharma")
- Levenshtein ratio
- Email prefix matching
"""

from __future__ import annotations

import re
from typing import Optional

from backend.app.core.analyzers.base import BaseAnalyzer
from backend.app.models.events import CalendarMetadata, EventType, MeetingEvent
from backend.app.models.evidence import EvidenceItem, SignalType
from backend.app.models.participant import ParticipantState


def _normalize(name: str) -> str:
    """Normalize a name for comparison."""
    return re.sub(r'[^a-z0-9\s]', '', name.lower().strip())


def _levenshtein_ratio(s1: str, s2: str) -> float:
    """Compute Levenshtein similarity ratio (0 to 1)."""
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    rows = len(s1) + 1
    cols = len(s2) + 1
    dist = [[0] * cols for _ in range(rows)]

    for i in range(rows):
        dist[i][0] = i
    for j in range(cols):
        dist[0][j] = j

    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dist[i][j] = min(
                dist[i - 1][j] + 1,
                dist[i][j - 1] + 1,
                dist[i - 1][j - 1] + cost,
            )

    max_len = max(len(s1), len(s2))
    return 1.0 - dist[rows - 1][cols - 1] / max_len


def _token_overlap(name1: str, name2: str) -> float:
    """Compute token overlap ratio between two names."""
    tokens1 = set(_normalize(name1).split())
    tokens2 = set(_normalize(name2).split())

    if not tokens1 or not tokens2:
        return 0.0

    overlap = tokens1 & tokens2
    return len(overlap) / max(len(tokens1), len(tokens2))


# Common device/generic names that are NOT real names
DEVICE_NAMES = {
    "macbook", "macbook pro", "macbook air", "iphone", "ipad",
    "pixel", "samsung", "oneplus", "windows", "user", "guest",
    "unknown", "participant", "android", "chrome", "firefox",
    "laptop", "desktop", "phone", "tablet", "home", "work",
}


def _is_device_name(name: str) -> bool:
    """Check if a display name is a device/generic name."""
    normalized = _normalize(name)
    return normalized in DEVICE_NAMES or any(d in normalized for d in DEVICE_NAMES)


class NameSimilarityAnalyzer(BaseAnalyzer):
    """Analyzes display name similarity to candidate information."""

    def __init__(self, weight: float = 15.0):
        super().__init__(weight)
        self._analyzed_names: dict[str, set[str]] = {}  # participant_id -> analyzed display names

    def get_signal_type(self) -> str:
        return SignalType.NAME_SIMILARITY

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

        # Trigger on join or display name change
        if event.event_type not in (EventType.PARTICIPANT_JOINED, EventType.DISPLAY_NAME_CHANGED):
            return evidence

        pid = event.participant_id
        if not pid or pid not in participants:
            return evidence

        participant = participants[pid]
        display_name = participant.display_name

        # Initialize tracking
        if pid not in self._analyzed_names:
            self._analyzed_names[pid] = set()

        # Skip if we already analyzed this display name
        if display_name in self._analyzed_names[pid]:
            return evidence

        self._analyzed_names[pid].add(display_name)

        candidate_name = calendar.candidate_name
        candidate_email = calendar.candidate_email or ""
        interviewer_names = calendar.interviewer_names or []

        # Check if this is a device name
        if _is_device_name(display_name):
            evidence.append(EvidenceItem(
                signal_type=SignalType.NAME_SIMILARITY,
                participant_id=pid,
                score=0.0,  # Neutral — no information
                weight=self.weight,
                confidence=0.8,
                reason=f"Display name '{display_name}' appears to be a device name — no name match possible",
                timestamp=event.timestamp,
                details={"display_name": display_name, "match_type": "device_name"},
            ))
            return evidence

        # 1. Exact match against candidate name
        norm_display = _normalize(display_name)
        norm_candidate = _normalize(candidate_name)

        if norm_display == norm_candidate:
            evidence.append(EvidenceItem(
                signal_type=SignalType.NAME_SIMILARITY,
                participant_id=pid,
                score=1.0,
                weight=self.weight,
                confidence=0.95,
                reason=f"Display name '{display_name}' exactly matches candidate name '{candidate_name}'",
                timestamp=event.timestamp,
                details={"match_type": "exact", "similarity": 1.0},
            ))
            return evidence

        # 2. Token overlap (handles partial names like "Priya S" vs "Priya Sharma")
        token_sim = _token_overlap(display_name, candidate_name)
        if token_sim > 0:
            score = min(token_sim * 1.2, 1.0)  # Boost partial matches
            evidence.append(EvidenceItem(
                signal_type=SignalType.NAME_SIMILARITY,
                participant_id=pid,
                score=score,
                weight=self.weight,
                confidence=token_sim,
                reason=f"Display name '{display_name}' partially matches candidate '{candidate_name}' (token overlap: {token_sim:.0%})",
                timestamp=event.timestamp,
                details={"match_type": "token_overlap", "similarity": token_sim},
            ))

        # 3. Levenshtein similarity
        lev_sim = _levenshtein_ratio(norm_display, norm_candidate)
        if lev_sim > 0.5 and token_sim == 0:  # Only if token didn't already match
            evidence.append(EvidenceItem(
                signal_type=SignalType.NAME_SIMILARITY,
                participant_id=pid,
                score=lev_sim * 0.8,
                weight=self.weight * 0.7,
                confidence=lev_sim,
                reason=f"Display name '{display_name}' is similar to candidate '{candidate_name}' (similarity: {lev_sim:.0%})",
                timestamp=event.timestamp,
                details={"match_type": "levenshtein", "similarity": lev_sim},
            ))

        # 4. Email prefix match
        if candidate_email:
            email_prefix = candidate_email.split("@")[0].replace(".", " ").replace("_", " ")
            email_sim = _token_overlap(display_name, email_prefix)
            if email_sim > 0.3:
                evidence.append(EvidenceItem(
                    signal_type=SignalType.NAME_SIMILARITY,
                    participant_id=pid,
                    score=email_sim * 0.7,
                    weight=self.weight * 0.6,
                    confidence=email_sim,
                    reason=f"Display name '{display_name}' matches candidate email prefix '{email_prefix}'",
                    timestamp=event.timestamp,
                    details={"match_type": "email", "similarity": email_sim},
                ))

        # 5. Check against interviewer names (negative evidence)
        for interviewer_name in interviewer_names:
            int_sim = _token_overlap(display_name, interviewer_name)
            lev_int = _levenshtein_ratio(norm_display, _normalize(interviewer_name))

            if int_sim > 0.5 or lev_int > 0.7:
                best_sim = max(int_sim, lev_int)
                evidence.append(EvidenceItem(
                    signal_type=SignalType.NAME_SIMILARITY,
                    participant_id=pid,
                    score=-best_sim,  # Negative — this is likely an interviewer
                    weight=self.weight,
                    confidence=best_sim,
                    reason=f"Display name '{display_name}' matches interviewer '{interviewer_name}' — likely NOT the candidate",
                    timestamp=event.timestamp,
                    details={"match_type": "interviewer_match", "interviewer": interviewer_name, "similarity": best_sim},
                ))

        # 6. If no match at all and not a device name
        if not evidence:
            evidence.append(EvidenceItem(
                signal_type=SignalType.NAME_SIMILARITY,
                participant_id=pid,
                score=-0.1,  # Slight negative — name doesn't match
                weight=self.weight * 0.3,
                confidence=0.4,
                reason=f"Display name '{display_name}' does not match candidate '{candidate_name}' or any interviewer",
                timestamp=event.timestamp,
                details={"match_type": "no_match"},
            ))

        return evidence

    def reset(self) -> None:
        self._analyzed_names.clear()
