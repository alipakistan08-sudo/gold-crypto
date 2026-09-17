"""Versioned JSON signal / proposal schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .enums import DecisionState, RiskDecision, Side


class AgentEvidence(BaseModel):
    agent: str
    timestamp: datetime
    symbol: str
    summary: str
    flags: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    data_quality_ok: bool = True


class TradeProposal(BaseModel):
    """Versioned trade proposal — agents emit this; risk engine sizes it."""

    schema_version: str = "signal-v1"
    signal_id: str
    created_at: datetime
    symbol: str
    venue: str = "paper-sim-v1"
    setup_id: str
    setup_version: str
    side: Side
    timeframe_regime: str = "1h"
    timeframe_structure: str = "15m"
    timeframe_execution: str = "5m"
    session: str
    regime: str
    vol_regime: str
    entry: float
    stop: float
    targets: list[float]
    planned_rr: float
    invalidation: str
    exclusions_checked: list[str] = Field(default_factory=list)
    evidence: list[AgentEvidence] = Field(default_factory=list)
    decision_state: DecisionState = DecisionState.NO_TRADE
    quality_score: float = Field(ge=0.0, le=1.0, default=0.5)
    notes: str = ""
    # Size is NEVER set by agents — risk engine fills these
    proposed_quantity: float | None = None
    spread: float | None = None
    atr_15m: float | None = None
    median_spread: float | None = None
    event_lock_active: bool = False

    @field_validator("targets")
    @classmethod
    def _targets_nonempty(cls, v: list[float]) -> list[float]:
        if not v:
            raise ValueError("targets must be non-empty for a trade proposal")
        return v


class RiskDecisionRecord(BaseModel):
    signal_id: str
    decision: RiskDecision
    reason_codes: list[str] = Field(default_factory=list)
    calculated_quantity: float = 0.0
    permitted_risk: float = 0.0
    planned_rr_after_costs: float | None = None
    risk_profile_version: str
    evaluated_at: datetime
    decision_state: DecisionState = DecisionState.NO_TRADE


def validate_proposal(data: dict[str, Any]) -> TradeProposal:
    return TradeProposal.model_validate(data)
