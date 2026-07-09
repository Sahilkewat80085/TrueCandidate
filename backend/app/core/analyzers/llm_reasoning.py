"""LLM Reasoning Analyzer — uses LLM for deep transcript understanding.

Only invoked when:
1. Enough transcript has accumulated
2. Ambiguity is high (top candidates are close in confidence)
3. Specific identity clues may be in natural language

Falls back gracefully when LLM is unavailable.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from backend.app.core.analyzers.base import BaseAnalyzer
from backend.app.models.events import CalendarMetadata, EventType, MeetingEvent
from backend.app.models.evidence import EvidenceItem, SignalType
from backend.app.models.participant import ParticipantState

logger = logging.getLogger(__name__)

LLM_PROMPT_TEMPLATE = """You are analyzing a meeting transcript to identify which participant is the interview CANDIDATE (the person being interviewed for a job).

Meeting Context:
- Expected candidate name: {candidate_name}
- Expected candidate email: {candidate_email}
- Interviewer names: {interviewer_names}
- Position: {position}

Participants in the meeting:
{participants_list}

Recent transcript:
{transcript}

Based on the transcript content, determine which participant is most likely the CANDIDATE being interviewed. Look for:
1. Self-introductions matching the candidate name
2. References to their own resume or work experience
3. Answering interview questions (vs asking them)
4. Expressions of interest in the role
5. Any identity-confirming statements

Respond in JSON format:
{{
    "candidate_id": "participant_id or null if uncertain",
    "confidence": 0.0 to 1.0,
    "reasons": ["reason1", "reason2"],
    "identity_clues": ["clue1", "clue2"],
    "interviewer_ids": ["id1", "id2"],
    "observer_ids": ["id1"]
}}
"""


class LLMReasoningAnalyzer(BaseAnalyzer):
    """Uses LLM to deeply analyze transcript for identity clues."""

    def __init__(self, weight: float = 15.0, enabled: bool = True, api_key: Optional[str] = None):
        super().__init__(weight)
        self._enabled = enabled
        self._api_key = api_key
        self._last_analysis_time: float = 0.0
        self._analysis_interval: float = 20.0  # Analyze every 20 seconds
        self._transcript_buffer: list[dict] = []
        self._min_transcript_chunks: int = 3  # Need at least 3 chunks
        self._last_result: Optional[dict] = None

    def get_signal_type(self) -> str:
        return SignalType.LLM_REASONING

    def analyze(
        self,
        event: MeetingEvent,
        participants: dict[str, ParticipantState],
        calendar: Optional[CalendarMetadata] = None,
        transcript_history: Optional[list] = None,
    ) -> list[EvidenceItem]:
        """Synchronous entry point — buffers transcripts and returns cached results."""
        evidence = []

        # Buffer transcript chunks
        if event.event_type == EventType.TRANSCRIPT_CHUNK:
            pid = event.participant_id
            text = event.data.get("text", "")
            if pid and text and pid in participants:
                self._transcript_buffer.append({
                    "speaker_id": pid,
                    "speaker_name": participants[pid].display_name,
                    "text": text,
                    "time": event.timestamp,
                })

        # Check if we should analyze
        should_analyze = (
            self._enabled
            and len(self._transcript_buffer) >= self._min_transcript_chunks
            and event.timestamp - self._last_analysis_time >= self._analysis_interval
        )

        if not should_analyze:
            return evidence

        self._last_analysis_time = event.timestamp

        # Use mock LLM analysis (pattern-based) when API key is not available
        # This provides similar intelligence without the API dependency
        if not self._api_key:
            return self._mock_llm_analysis(participants, calendar, event.timestamp)

        # Real LLM analysis would be async — for sync interface, return cached
        # The actual LLM call happens in the async variant
        return evidence

    async def analyze_async(
        self,
        participants: dict[str, ParticipantState],
        calendar: Optional[CalendarMetadata] = None,
        timestamp: float = 0.0,
    ) -> list[EvidenceItem]:
        """Async LLM analysis — called by the engine when appropriate."""
        if not self._enabled or not self._api_key:
            return self._mock_llm_analysis(participants, calendar, timestamp)

        try:
            result = await self._call_llm(participants, calendar)
            if result:
                self._last_result = result
                return self._process_llm_result(result, participants, timestamp)
        except Exception as e:
            logger.warning(f"LLM analysis failed, falling back to mock: {e}")
            return self._mock_llm_analysis(participants, calendar, timestamp)

        return []

    def _mock_llm_analysis(
        self,
        participants: dict[str, ParticipantState],
        calendar: Optional[CalendarMetadata],
        timestamp: float,
    ) -> list[EvidenceItem]:
        """Pattern-based analysis that simulates LLM reasoning."""
        evidence = []

        if not self._transcript_buffer:
            return evidence

        # Analyze transcript patterns per participant
        participant_texts: dict[str, list[str]] = {}
        for chunk in self._transcript_buffer:
            pid = chunk["speaker_id"]
            if pid not in participant_texts:
                participant_texts[pid] = []
            participant_texts[pid].append(chunk["text"].lower())

        for pid, texts in participant_texts.items():
            if pid not in participants:
                continue
            p = participants[pid]
            all_text = " ".join(texts)

            # Count candidate-like signals in their speech
            candidate_signals = 0
            interviewer_signals = 0
            reasons = []

            # Check for experience sharing (candidate behavior)
            experience_words = ["i worked", "my experience", "i built", "i designed",
                                "i led", "i managed", "my project", "i developed",
                                "in my role", "i learned", "i implemented"]
            for word in experience_words:
                if word in all_text:
                    candidate_signals += 1
                    reasons.append(f"Shares personal experience: '{word}'")

            # Check for question-asking (interviewer behavior)
            question_markers = ["can you tell", "how would you", "what is your",
                                "describe a time", "walk me through", "why did you",
                                "what are your", "how do you handle"]
            for marker in question_markers:
                if marker in all_text:
                    interviewer_signals += 1

            if candidate_signals > interviewer_signals and candidate_signals >= 2:
                score = min(candidate_signals * 0.15, 0.8)
                evidence.append(EvidenceItem(
                    signal_type=SignalType.LLM_REASONING,
                    participant_id=pid,
                    score=score,
                    weight=self.weight,
                    confidence=min(0.5 + candidate_signals * 0.1, 0.85),
                    reason=f"Transcript analysis: '{p.display_name}' shares personal experiences ({candidate_signals} signals) — candidate pattern",
                    timestamp=timestamp,
                    details={"candidate_signals": candidate_signals, "reasons": reasons[:3]},
                ))
            elif interviewer_signals > candidate_signals and interviewer_signals >= 2:
                score = -0.5
                evidence.append(EvidenceItem(
                    signal_type=SignalType.LLM_REASONING,
                    participant_id=pid,
                    score=score,
                    weight=self.weight * 0.8,
                    confidence=min(0.5 + interviewer_signals * 0.1, 0.8),
                    reason=f"Transcript analysis: '{p.display_name}' asks probing questions ({interviewer_signals} signals) — interviewer pattern",
                    timestamp=timestamp,
                    details={"interviewer_signals": interviewer_signals},
                ))

        return evidence

    async def _call_llm(
        self,
        participants: dict[str, ParticipantState],
        calendar: Optional[CalendarMetadata],
    ) -> Optional[dict]:
        """Call the LLM API for transcript analysis."""
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self._api_key)

            # Build prompt
            participants_list = "\n".join(
                f"- {pid}: '{p.display_name}' (speaking: {p.total_speaking_duration:.0f}s, words: {p.transcript_word_count})"
                for pid, p in participants.items() if p.is_active
            )

            transcript = "\n".join(
                f"[{chunk['time']:.0f}s] {chunk['speaker_name']}: {chunk['text']}"
                for chunk in self._transcript_buffer[-20:]  # Last 20 chunks
            )

            prompt = LLM_PROMPT_TEMPLATE.format(
                candidate_name=calendar.candidate_name if calendar else "Unknown",
                candidate_email=calendar.candidate_email or "N/A",
                interviewer_names=", ".join(calendar.interviewer_names) if calendar else "Unknown",
                position=calendar.position or "Unknown",
                participants_list=participants_list,
                transcript=transcript,
            )

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            return json.loads(content) if content else None

        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            return None

    def _process_llm_result(
        self,
        result: dict,
        participants: dict[str, ParticipantState],
        timestamp: float,
    ) -> list[EvidenceItem]:
        """Convert LLM result to evidence items."""
        evidence = []

        candidate_id = result.get("candidate_id")
        confidence = result.get("confidence", 0.5)
        reasons = result.get("reasons", [])
        interviewer_ids = result.get("interviewer_ids", [])

        if candidate_id and candidate_id in participants:
            p = participants[candidate_id]
            evidence.append(EvidenceItem(
                signal_type=SignalType.LLM_REASONING,
                participant_id=candidate_id,
                score=confidence,
                weight=self.weight,
                confidence=confidence,
                reason=f"LLM analysis identifies '{p.display_name}' as candidate: {'; '.join(reasons[:2])}",
                timestamp=timestamp,
                details={"llm_reasons": reasons, "llm_confidence": confidence},
            ))

        for int_id in interviewer_ids:
            if int_id in participants:
                p = participants[int_id]
                evidence.append(EvidenceItem(
                    signal_type=SignalType.LLM_REASONING,
                    participant_id=int_id,
                    score=-0.6,
                    weight=self.weight * 0.8,
                    confidence=0.7,
                    reason=f"LLM analysis identifies '{p.display_name}' as interviewer",
                    timestamp=timestamp,
                    details={"role": "interviewer"},
                ))

        return evidence

    def reset(self) -> None:
        self._last_analysis_time = 0.0
        self._transcript_buffer.clear()
        self._last_result = None
