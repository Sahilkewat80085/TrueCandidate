"""Configuration management for TrueCandidate."""

from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel, Field


class SignalWeights(BaseModel):
    """Configurable weights for each signal type."""
    name_similarity: float = 15.0
    calendar_match: float = 20.0
    speech_pattern: float = 10.0
    transcript_evidence: float = 25.0
    behavioral: float = 10.0
    temporal: float = 5.0
    llm_reasoning: float = 15.0


class PenaltyWeights(BaseModel):
    """Penalty weights for negative evidence."""
    display_name_changed: float = -5.0
    frequent_rejoin: float = -3.0
    silent_participant: float = -2.0
    screen_sharing: float = -4.0


class ConfidenceConfig(BaseModel):
    """Configuration for the confidence engine."""
    smoothing_alpha: float = 0.3
    temporal_decay_halflife: float = 120.0  # seconds
    low_threshold: float = 0.4
    medium_threshold: float = 0.7
    high_threshold: float = 0.9
    logistic_k: float = 5.0
    logistic_midpoint: float = 0.5


class LLMConfig(BaseModel):
    """LLM configuration."""
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    enabled: bool = True
    max_tokens: int = 500
    temperature: float = 0.3
    analysis_interval: float = 15.0  # seconds between LLM analyses


class AppConfig(BaseModel):
    """Root application configuration."""
    app_name: str = "TrueCandidate"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"])

    # Engine config
    signal_weights: SignalWeights = Field(default_factory=SignalWeights)
    penalty_weights: PenaltyWeights = Field(default_factory=PenaltyWeights)
    confidence: ConfidenceConfig = Field(default_factory=ConfidenceConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)

    # Mock connector config
    scenario_speed: float = 1.0  # 1.0 = realtime, 2.0 = 2x speed
    scenario_dir: str = "scenarios"


def load_config() -> AppConfig:
    """Load configuration from environment variables."""
    config = AppConfig(
        debug=os.getenv("DEBUG", "false").lower() == "true",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )

    # LLM config from env
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        config.llm.api_key = api_key
    else:
        config.llm.enabled = False

    speed = os.getenv("SCENARIO_SPEED")
    if speed:
        config.scenario_speed = float(speed)

    return config
