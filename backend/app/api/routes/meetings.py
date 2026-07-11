"""Meeting API routes — REST endpoints for meeting management."""

from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from backend.app.models.events import CalendarMetadata, MeetingEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/meetings", tags=["meetings"])

# Regular expressions for parameter validation
MEETING_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
MEETING_CODE_PATTERN = re.compile(r"^[a-z]{3}-[a-z]{4}-[a-z]{3}$")

def validate_meeting_id(meeting_id: str) -> None:
    if not MEETING_ID_PATTERN.match(meeting_id):
        raise HTTPException(status_code=400, detail="Invalid meeting ID format")

def validate_meeting_code(meeting_code: str) -> None:
    if not MEETING_CODE_PATTERN.match(meeting_code.lower()):
        raise HTTPException(status_code=400, detail="Invalid meeting code format")


# Mock Database matching Google Meet codes to Candidate Calendar details
CALENDAR_REGISTRY = {
    "abc-defg-hij": {
        "candidate_name": "Priya Sharma",
        "candidate_email": "priya.sharma@gmail.com",
        "interviewer_names": ["Alex Chen"],
        "position": "Software Engineer Intern"
    },
    "qwe-rtyu-iop": {
        "candidate_name": "Samantha Patel",
        "candidate_email": "samantha.patel@outlook.com",
        "interviewer_names": ["David Kim"],
        "position": "Backend Developer"
    },
    "zxc-vbnm-asd": {
        "candidate_name": "Rahul Gupta",
        "candidate_email": "rahul.gupta@gmail.com",
        "interviewer_names": ["Sarah Johnson"],
        "position": "Full Stack Developer"
    }
}


@router.get("/calendar/{meeting_code}", response_model=CalendarMetadata)
async def get_calendar_by_code(meeting_code: str):
    """Retrieve candidate calendar metadata automatically based on the Google Meet code."""
    validate_meeting_code(meeting_code)
    # Lookup in registry, default to a fallback candidate if code not registered
    data = CALENDAR_REGISTRY.get(meeting_code.lower())
    if not data:
        # Generate a dynamic fallback so it works for any random Meet link
        data = {
            "candidate_name": "Jane Doe",
            "candidate_email": "jane.doe@live.com",
            "interviewer_names": ["Alex Chen"],
            "position": "Software Engineer (Live Demo)"
        }
    return CalendarMetadata(**data)


class StartScenarioRequest(BaseModel):
    scenario_id: str
    speed: float = 5.0  # Default: 5x speed for demo


class StartScenarioResponse(BaseModel):
    meeting_id: str
    scenario_id: str
    message: str


@router.post("/start", response_model=StartScenarioResponse)
async def start_scenario(request: StartScenarioRequest):
    """Start a scenario simulation."""
    from backend.app.main import app_state

    # Sanitize scenario_id to prevent directory traversal
    if not re.match(r"^[a-zA-Z0-9_-]+$", request.scenario_id):
        raise HTTPException(status_code=400, detail="Invalid scenario ID format")

    try:
        meeting_id = await app_state.session_manager.start_scenario(
            scenario_id=request.scenario_id,
            update_callback=app_state.on_meeting_update,
            speed=request.speed,
        )
        return StartScenarioResponse(
            meeting_id=meeting_id,
            scenario_id=request.scenario_id,
            message=f"Scenario '{request.scenario_id}' started",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start scenario: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{meeting_id}/stop")
async def stop_meeting(meeting_id: str):
    """Stop an active meeting session."""
    validate_meeting_id(meeting_id)
    from backend.app.main import app_state

    await app_state.session_manager.stop_session(meeting_id)
    return {"message": f"Meeting {meeting_id} stopped"}


@router.get("/{meeting_id}/prediction")
async def get_prediction(meeting_id: str):
    """Get current candidate prediction."""
    validate_meeting_id(meeting_id)
    from backend.app.main import app_state

    prediction = app_state.session_manager.get_prediction(meeting_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Meeting not found or no prediction yet")
    return prediction


@router.get("/{meeting_id}/confidence-timeline")
async def get_confidence_timeline(meeting_id: str):
    """Get the full confidence timeline for a meeting."""
    validate_meeting_id(meeting_id)
    from backend.app.main import app_state

    engine = app_state.session_manager.get_engine(meeting_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Meeting not found")

    timeline = engine.confidence.get_timeline()
    return {"meeting_id": meeting_id, "points": [p.model_dump() for p in timeline]}


@router.get("/{meeting_id}/explanation")
async def get_explanation(meeting_id: str):
    """Get detailed explanation for the current prediction."""
    validate_meeting_id(meeting_id)
    from backend.app.main import app_state

    prediction = app_state.session_manager.get_prediction(meeting_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return prediction.model_dump()


@router.get("/{meeting_id}/participants")
async def get_participants(meeting_id: str):
    """Get all participants with their current scores."""
    validate_meeting_id(meeting_id)
    from backend.app.main import app_state

    engine = app_state.session_manager.get_engine(meeting_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Meeting not found")

    participants = []
    for pid, p in engine.participants.items():
        conf = engine.confidence.get_confidence(pid)
        participants.append({
            "participant_id": pid,
            "display_name": p.display_name,
            "is_active": p.is_active,
            "webcam_on": p.webcam_on,
            "is_speaking": p.is_speaking,
            "confidence": conf,
            "total_speaking_duration": p.total_speaking_duration,
            "transcript_word_count": p.transcript_word_count,
        })

    return {"meeting_id": meeting_id, "participants": participants}


@router.get("/{meeting_id}/events")
async def get_events(meeting_id: str, limit: int = Query(50, ge=1, le=500)):
    """Get recent meeting events."""
    validate_meeting_id(meeting_id)
    from backend.app.main import app_state

    session = app_state.session_manager.get_session(meeting_id)
    if not session:
        raise HTTPException(status_code=404, detail="Meeting not found")

    events = session["events"][-limit:]
    return {
        "meeting_id": meeting_id,
        "events": [e.model_dump() for e in events],
        "total_events": len(session["events"]),
    }


@router.get("/{meeting_id}/transcript")
async def get_transcript(meeting_id: str):
    """Get the full transcript."""
    validate_meeting_id(meeting_id)
    from backend.app.main import app_state

    engine = app_state.session_manager.get_engine(meeting_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return {
        "meeting_id": meeting_id,
        "transcript": engine.transcript_history,
    }


@router.get("/")
async def list_meetings():
    """List all active meeting sessions."""
    from backend.app.main import app_state

    return {"meetings": app_state.session_manager.list_active_sessions()}


class StartCustomMeetingResponse(BaseModel):
    meeting_id: str
    message: str


@router.post("/start_custom", response_model=StartCustomMeetingResponse)
async def start_custom_meeting(calendar: CalendarMetadata):
    """Start an empty custom live meeting session."""
    from backend.app.main import app_state

    try:
        meeting_id = await app_state.session_manager.start_custom_meeting(
            calendar=calendar,
            update_callback=app_state.on_meeting_update,
        )
        return StartCustomMeetingResponse(
            meeting_id=meeting_id,
            message="Custom live meeting session initialized successfully",
        )
    except Exception as e:
        logger.error(f"Failed to start custom meeting: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{meeting_id}/event")
async def push_event(meeting_id: str, event: MeetingEvent):
    """Push a normalized live meeting event (e.g. from Chrome Extension)."""
    validate_meeting_id(meeting_id)
    from backend.app.main import app_state

    session = app_state.session_manager.get_session(meeting_id)
    if not session:
        raise HTTPException(status_code=404, detail="Meeting session not found")

    try:
        engine = session["engine"]
        prediction = engine.process_event(event)
        session["events"].append(event)
        if prediction:
            session["predictions"].append(prediction)
        return {"status": "success", "prediction": prediction}
    except Exception as e:
        logger.error(f"Failed to process pushed event for {meeting_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
