"""Abstract base class for all signal analyzers.

Every analyzer implements this interface to produce EvidenceItems
from normalized meeting events. Analyzers are independent — they
don't know about each other.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from backend.app.models.events import CalendarMetadata, MeetingEvent
from backend.app.models.evidence import EvidenceItem
from backend.app.models.participant import ParticipantState


class BaseAnalyzer(ABC):
    """Base class for all signal analyzers.
    
    Each analyzer:
    1. Receives meeting events
    2. Maintains internal state
    3. Produces EvidenceItems with scores, weights, and reasons
    """

    def __init__(self, weight: float = 10.0):
        self.weight = weight
        self.name: str = self.__class__.__name__

    @abstractmethod
    def analyze(
        self,
        event: MeetingEvent,
        participants: dict[str, ParticipantState],
        calendar: Optional[CalendarMetadata] = None,
        transcript_history: Optional[list] = None,
    ) -> list[EvidenceItem]:
        """Analyze an event and produce evidence items.
        
        Args:
            event: The normalized meeting event
            participants: Current state of all participants
            calendar: External calendar metadata (if available)
            transcript_history: Full transcript so far (if needed)
            
        Returns:
            List of EvidenceItems (may be empty if no evidence from this event)
        """
        ...

    @abstractmethod
    def get_signal_type(self) -> str:
        """Return the signal type this analyzer produces."""
        ...

    def reset(self) -> None:
        """Reset analyzer state for a new meeting."""
        pass
