"""Meeting API routes — REST endpoints for meeting management."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


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
    from backend.app.main import app_state

    await app_state.session_manager.stop_session(meeting_id)
    return {"message": f"Meeting {meeting_id} stopped"}


@router.get("/{meeting_id}/prediction")
async def get_prediction(meeting_id: str):
    """Get current candidate prediction."""
    from backend.app.main import app_state

    prediction = app_state.session_manager.get_prediction(meeting_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Meeting not found or no prediction yet")
    return prediction


@router.get("/{meeting_id}/confidence-timeline")
async def get_confidence_timeline(meeting_id: str):
    """Get the full confidence timeline for a meeting."""
    from backend.app.main import app_state

    engine = app_state.session_manager.get_engine(meeting_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Meeting not found")

    timeline = engine.confidence.get_timeline()
    return {"meeting_id": meeting_id, "points": [p.model_dump() for p in timeline]}


@router.get("/{meeting_id}/explanation")
async def get_explanation(meeting_id: str):
    """Get detailed explanation for the current prediction."""
    from backend.app.main import app_state

    prediction = app_state.session_manager.get_prediction(meeting_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return prediction.model_dump()


@router.get("/{meeting_id}/participants")
async def get_participants(meeting_id: str):
    """Get all participants with their current scores."""
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
