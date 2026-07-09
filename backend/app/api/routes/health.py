"""Health check route."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "TrueCandidate"}


@router.get("/")
async def root():
    return {
        "service": "TrueCandidate",
        "version": "1.0.0",
        "description": "AI-powered interview candidate identification system",
        "docs": "/docs",
    }
