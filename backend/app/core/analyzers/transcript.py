"""Transcript Analyzer — extracts identity clues from speaker-attributed transcript.

Detects:
- Self-introductions ("Hi, I'm Priya")
- Resume references ("In my previous role at Google...")
- Answering identity questions ("Yes, I'm the candidate")
- Question-asking patterns (interviewers ask, candidates answer)
- Role references ("I applied for the SWE position")
"""

from __future__ import annotations

import re
from typing import Optional

from backend.app.core.analyzers.base import BaseAnalyzer
from backend.app.models.events import CalendarMetadata, EventType, MeetingEvent
from backend.app.models.evidence import EvidenceItem, SignalType
from backend.app.models.participant import ParticipantState


# Patterns that suggest the speaker IS the candidate
CANDIDATE_PATTERNS = [
    (r"(?:i'?m|my name is|this is)\s+(\w+)", "self_introduction", 0.8),
    (r"(?:i applied|i'm applying|i'm interviewing)\s+(?:for|to)", "applied_for_role", 0.9),
    (r"(?:my (?:previous|last|current) (?:role|job|position|company))", "resume_reference", 0.7),
    (r"(?:i (?:worked|work|was working) (?:at|for|with))", "work_experience", 0.7),
    (r"(?:my (?:experience|background|expertise) (?:is|includes|involves))", "experience_reference", 0.7),
    (r"(?:i (?:graduated|studied|majored) (?:from|in|at))", "education_reference", 0.6),
    (r"(?:in my (?:resume|cv|portfolio))", "resume_mention", 0.8),
    (r"(?:yes,?\s*(?:i am|that'?s me|i'm)\s+(?:the candidate|here for))", "identity_confirmation", 0.95),
    (r"(?:thank you for (?:having|interviewing|considering) me)", "candidate_gratitude", 0.7),
    (r"(?:i'm (?:excited|interested|passionate) about (?:this|the) (?:role|position|opportunity))", "role_interest", 0.75),
]

# Patterns that suggest the speaker is an INTERVIEWER
INTERVIEWER_PATTERNS = [
    (r"(?:welcome|thanks for (?:joining|coming))", "interviewer_welcome", 0.7),
    (r"(?:tell (?:me|us) about (?:yourself|your))", "interview_question", 0.8),
    (r"(?:can you (?:walk|tell|explain|describe))", "probing_question", 0.6),
    (r"(?:(?:i|we) (?:have|had) (?:a few|some) questions)", "question_setup", 0.7),
    (r"(?:are you (?:the candidate|\w+ \w+)\?)", "identity_question", 0.75),
    (r"(?:let me (?:introduce|share) (?:myself|the team|about))", "interviewer_intro", 0.6),
    (r"(?:(?:i'm|we're) (?:from|with|at) (?:the|our) (?:team|company))", "company_reference", 0.65),
    (r"(?:(?:next|final) (?:question|round|step))", "interview_structure", 0.6),
]


class TranscriptAnalyzer(BaseAnalyzer):
    """Analyzes transcript content for candidate identity clues."""

    def __init__(self, weight: float = 25.0):
        super().__init__(weight)
        self._question_askers: dict[str, int] = {}  # pid -> question count
        self._answer_givers: dict[str, int] = {}    # pid -> answer count
        self._last_speaker_asked_question: Optional[str] = None

    def get_signal_type(self) -> str:
        return SignalType.TRANSCRIPT_EVIDENCE

    def analyze(
        self,
        event: MeetingEvent,
        participants: dict[str, ParticipantState],
        calendar: Optional[CalendarMetadata] = None,
        transcript_history: Optional[list] = None,
    ) -> list[EvidenceItem]:
        evidence = []

        if event.event_type != EventType.TRANSCRIPT_CHUNK:
            return evidence

        pid = event.participant_id
        text = event.data.get("text", "")

        if not pid or not text or pid not in participants:
            return evidence

        participant = participants[pid]
        text_lower = text.lower().strip()

        # Update word count
        participant.transcript_word_count += len(text.split())

        # Check candidate patterns
        for pattern, pattern_name, base_confidence in CANDIDATE_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                # Check if self-introduction name matches candidate
                extra_boost = 0.0
                reason_suffix = ""
                if pattern_name == "self_introduction" and calendar:
                    intro_name = match.group(1) if match.lastindex else ""
                    from backend.app.core.analyzers.name_similarity import _token_overlap
                    name_sim = _token_overlap(intro_name, calendar.candidate_name)
                    if name_sim > 0.3:
                        extra_boost = 0.2
                        reason_suffix = f" — name '{intro_name}' matches candidate '{calendar.candidate_name}'"

                evidence.append(EvidenceItem(
                    signal_type=SignalType.TRANSCRIPT_EVIDENCE,
                    participant_id=pid,
                    score=0.7 + extra_boost,
                    weight=self.weight,
                    confidence=min(base_confidence + extra_boost, 0.98),
                    reason=f"'{participant.display_name}' transcript: {pattern_name.replace('_', ' ')}{reason_suffix}",
                    timestamp=event.timestamp,
                    details={"pattern": pattern_name, "text_excerpt": text[:100], "matched": match.group(0)},
                ))

        # Check interviewer patterns
        for pattern, pattern_name, base_confidence in INTERVIEWER_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                evidence.append(EvidenceItem(
                    signal_type=SignalType.TRANSCRIPT_EVIDENCE,
                    participant_id=pid,
                    score=-0.6,
                    weight=self.weight * 0.8,
                    confidence=base_confidence,
                    reason=f"'{participant.display_name}' shows interviewer behavior: {pattern_name.replace('_', ' ')}",
                    timestamp=event.timestamp,
                    details={"pattern": pattern_name, "text_excerpt": text[:100]},
                ))

        # Question detection — interviewers ask more questions
        if text_lower.rstrip().endswith("?"):
            self._question_askers[pid] = self._question_askers.get(pid, 0) + 1
            self._last_speaker_asked_question = pid
        elif self._last_speaker_asked_question and self._last_speaker_asked_question != pid:
            # This person is answering a question from someone else
            self._answer_givers[pid] = self._answer_givers.get(pid, 0) + 1
            self._last_speaker_asked_question = None

        # Periodically produce evidence from Q&A patterns
        total_questions = sum(self._question_askers.values())
        total_answers = sum(self._answer_givers.values())

        if total_questions >= 2 and total_answers >= 2:
            answers = self._answer_givers.get(pid, 0)
            questions = self._question_askers.get(pid, 0)

            if answers > questions and answers >= 2:
                ratio = answers / max(answers + questions, 1)
                evidence.append(EvidenceItem(
                    signal_type=SignalType.TRANSCRIPT_EVIDENCE,
                    participant_id=pid,
                    score=ratio * 0.6,
                    weight=self.weight * 0.6,
                    confidence=min(ratio, 0.8),
                    reason=f"'{participant.display_name}' answers more questions ({answers}) than asks ({questions}) — candidate pattern",
                    timestamp=event.timestamp,
                    details={"answers": answers, "questions": questions, "ratio": ratio},
                ))
            elif questions > answers and questions >= 2:
                ratio = questions / max(answers + questions, 1)
                evidence.append(EvidenceItem(
                    signal_type=SignalType.TRANSCRIPT_EVIDENCE,
                    participant_id=pid,
                    score=-ratio * 0.5,
                    weight=self.weight * 0.5,
                    confidence=min(ratio, 0.7),
                    reason=f"'{participant.display_name}' asks more questions ({questions}) than answers ({answers}) — interviewer pattern",
                    timestamp=event.timestamp,
                    details={"answers": answers, "questions": questions},
                ))

        return evidence

    def reset(self) -> None:
        self._question_askers.clear()
        self._answer_givers.clear()
        self._last_speaker_asked_question = None
