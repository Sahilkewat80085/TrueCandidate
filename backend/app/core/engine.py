"""Core Engine — the main orchestrator that ties everything together.

This is the central nervous system of TrueCandidate:
1. Receives events from the Meeting Connector
2. Updates participant state
3. Runs all signal analyzers
4. Feeds evidence into the fusion engine
5. Updates confidence scores
6. Generates predictions with explanations
7. Broadcasts updates via callback
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from backend.app.config import AppConfig
from backend.app.confidence.confidence_engine import ConfidenceEngine
from backend.app.core.analyzers.base import BaseAnalyzer
from backend.app.core.analyzers.behavioral import BehavioralAnalyzer
from backend.app.core.analyzers.calendar_match import CalendarMatchAnalyzer
from backend.app.core.analyzers.llm_reasoning import LLMReasoningAnalyzer
from backend.app.core.analyzers.name_similarity import NameSimilarityAnalyzer
from backend.app.core.analyzers.speech_pattern import SpeechPatternAnalyzer
from backend.app.core.analyzers.temporal import TemporalAnalyzer
from backend.app.core.analyzers.transcript import TranscriptAnalyzer
from backend.app.explainability.explainer import ExplainabilityEngine
from backend.app.fusion.fusion_engine import FusionEngine
from backend.app.models.events import CalendarMetadata, EventType, MeetingEvent
from backend.app.models.evidence import EvidenceItem
from backend.app.models.participant import ParticipantState
from backend.app.models.prediction import CandidatePrediction

logger = logging.getLogger(__name__)


class IdentificationEngine:
    """Main orchestrator for candidate identification."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()

        # Core engines
        self.fusion = FusionEngine(self.config)
        self.confidence = ConfidenceEngine(self.config)
        self.explainer = ExplainabilityEngine(self.fusion, self.confidence)

        # Signal analyzers
        weights = self.config.signal_weights
        self.analyzers: list[BaseAnalyzer] = [
            NameSimilarityAnalyzer(weight=weights.name_similarity),
            CalendarMatchAnalyzer(weight=weights.calendar_match),
            SpeechPatternAnalyzer(weight=weights.speech_pattern),
            TranscriptAnalyzer(weight=weights.transcript_evidence),
            BehavioralAnalyzer(weight=weights.behavioral),
            TemporalAnalyzer(weight=weights.temporal),
            LLMReasoningAnalyzer(
                weight=weights.llm_reasoning,
                enabled=self.config.llm.enabled,
                api_key=self.config.llm.api_key,
            ),
        ]

        # State
        self.participants: dict[str, ParticipantState] = {}
        self.calendar: Optional[CalendarMetadata] = None
        self.transcript_history: list[dict] = []
        self.meeting_id: str = ""
        self.all_evidence: list[EvidenceItem] = []
        self.all_events: list[MeetingEvent] = []

        # Callbacks for real-time updates
        self._update_callbacks: list[Callable] = []

    def set_calendar(self, calendar: CalendarMetadata) -> None:
        """Set calendar metadata for the meeting."""
        self.calendar = calendar
        logger.info(f"Calendar set: candidate='{calendar.candidate_name}', interviewers={calendar.interviewer_names}")

    def on_update(self, callback: Callable) -> None:
        """Register a callback for prediction updates."""
        self._update_callbacks.append(callback)

    def process_event(self, event: MeetingEvent) -> Optional[CandidatePrediction]:
        """Process a single meeting event through the full pipeline.
        
        Args:
            event: Normalized meeting event
            
        Returns:
            Updated CandidatePrediction (or None if no change)
        """
        self.all_events.append(event)

        # Step 1: Update participant state
        self._update_participant_state(event)

        # Step 2: Run all analyzers
        all_evidence = []
        for analyzer in self.analyzers:
            try:
                evidence = analyzer.analyze(
                    event=event,
                    participants=self.participants,
                    calendar=self.calendar,
                    transcript_history=self.transcript_history,
                )
                all_evidence.extend(evidence)
            except Exception as e:
                logger.error(f"Analyzer {analyzer.name} failed: {e}", exc_info=True)

        # Step 3: Feed evidence into fusion engine
        if all_evidence:
            self.all_evidence.extend(all_evidence)
            probs = self.fusion.update_batch(all_evidence)

            # Step 4: Update confidence
            event_desc = self._event_description(event)
            self.confidence.update(probs, event.timestamp, event_desc)

        # Step 5: Generate prediction
        prediction = self.explainer.generate_prediction(
            meeting_id=self.meeting_id,
            participants=self.participants,
            timestamp=event.timestamp,
        )

        # Step 6: Notify callbacks
        for callback in self._update_callbacks:
            try:
                callback(prediction, event, all_evidence)
            except Exception as e:
                logger.error(f"Update callback failed: {e}")

        return prediction

    def get_current_prediction(self) -> CandidatePrediction:
        """Get the current prediction without processing new events."""
        return self.explainer.generate_prediction(
            meeting_id=self.meeting_id,
            participants=self.participants,
            timestamp=self.all_events[-1].timestamp if self.all_events else 0.0,
        )

    def _update_participant_state(self, event: MeetingEvent) -> None:
        """Update participant state from an event."""
        pid = event.participant_id
        if not pid:
            return

        if event.event_type == EventType.PARTICIPANT_JOINED:
            display_name = event.data.get("display_name", f"Participant {pid}")
            if pid not in self.participants:
                self.participants[pid] = ParticipantState(
                    participant_id=pid,
                    display_name=display_name,
                    join_time=event.timestamp,
                )
                self.fusion.add_participant(pid)
                logger.info(f"Participant joined: {pid} as '{display_name}'")
            else:
                self.participants[pid].is_active = True

        elif event.event_type == EventType.PARTICIPANT_LEFT:
            if pid in self.participants:
                self.participants[pid].is_active = False
                self.participants[pid].leave_time = event.timestamp

        elif event.event_type == EventType.DISPLAY_NAME_CHANGED:
            if pid in self.participants:
                old = self.participants[pid].display_name
                new = event.data.get("new_name", event.data.get("display_name", old))
                self.participants[pid].display_name_history.append(old)
                self.participants[pid].display_name = new

        elif event.event_type == EventType.WEBCAM_ENABLED:
            if pid in self.participants:
                self.participants[pid].webcam_on = True

        elif event.event_type == EventType.WEBCAM_DISABLED:
            if pid in self.participants:
                self.participants[pid].webcam_on = False

        elif event.event_type == EventType.SPEAKING_STARTED:
            if pid in self.participants:
                self.participants[pid].is_speaking = True

        elif event.event_type == EventType.SPEAKING_STOPPED:
            if pid in self.participants:
                self.participants[pid].is_speaking = False

        elif event.event_type == EventType.TRANSCRIPT_CHUNK:
            text = event.data.get("text", "")
            if pid in self.participants and text:
                self.transcript_history.append({
                    "speaker_id": pid,
                    "speaker_name": self.participants[pid].display_name,
                    "text": text,
                    "time": event.timestamp,
                })

        elif event.event_type == EventType.SCREEN_SHARE_STARTED:
            if pid in self.participants:
                self.participants[pid].is_screen_sharing = True

        elif event.event_type == EventType.SCREEN_SHARE_STOPPED:
            if pid in self.participants:
                self.participants[pid].is_screen_sharing = False

    def _event_description(self, event: MeetingEvent) -> str:
        """Generate a short description for an event."""
        pid = event.participant_id
        name = self.participants.get(pid, ParticipantState(
            participant_id=pid or "", display_name="Unknown"
        )).display_name if pid else "System"

        descriptions = {
            EventType.PARTICIPANT_JOINED: f"'{name}' joined",
            EventType.PARTICIPANT_LEFT: f"'{name}' left",
            EventType.DISPLAY_NAME_CHANGED: f"'{name}' changed name",
            EventType.SPEAKING_STARTED: f"'{name}' started speaking",
            EventType.SPEAKING_STOPPED: f"'{name}' stopped speaking",
            EventType.WEBCAM_ENABLED: f"'{name}' enabled webcam",
            EventType.WEBCAM_DISABLED: f"'{name}' disabled webcam",
            EventType.TRANSCRIPT_CHUNK: f"'{name}' said something",
            EventType.SCREEN_SHARE_STARTED: f"'{name}' started screen share",
            EventType.SCREEN_SHARE_STOPPED: f"'{name}' stopped screen share",
        }

        return descriptions.get(event.event_type, f"Event: {event.event_type}")

    def reset(self) -> None:
        """Reset everything for a new meeting."""
        self.participants.clear()
        self.calendar = None
        self.transcript_history.clear()
        self.all_evidence.clear()
        self.all_events.clear()
        self.fusion.reset()
        self.confidence.reset()
        for analyzer in self.analyzers:
            analyzer.reset()
        logger.info("Engine reset for new meeting")
