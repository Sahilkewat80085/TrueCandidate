"""Scenario API routes."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.get("/")
async def list_scenarios():
    """List all available scenarios."""
    from backend.app.main import app_state

    scenarios = app_state.session_manager.list_scenarios()
    return {"scenarios": scenarios}


@router.get("/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Get details of a specific scenario."""
    from backend.app.main import app_state

    scenarios = app_state.session_manager.list_scenarios()
    for s in scenarios:
        if s["id"] == scenario_id:
            return s

    return {"error": "Scenario not found"}
