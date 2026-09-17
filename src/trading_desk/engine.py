"""Deterministic risk engine — authoritative for size and APPROVE/REJECT/REDUCE/DEFER."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from trading_desk.models.enums import DecisionState, RiskDecision
from trading_desk.models.signal import RiskDecisionRecord, TradeProposal
from trading_desk.risk.kill_switch import KillSwitch


@dataclass
class RiskState:
    equity: float
    realized_pnl_today: float = 0.0
    open_risk: float = 0.0
    open_positions: int = 0
    positions_by_symbol: dict[str, int] = field(default_factory=dict)
    loss_streak: int = 0


class RiskEngine:
    def __init__(self, cfg: dict[str, Any], kill_switch: KillSwitch):
        self.cfg = cfg
        self.risk = cfg["risk"]
        self.paper = cfg["paper"]
        self.profile_version = cfg["desk"]["risk_profile_version"]
        self.kill_switch = kill_switch

    def evaluate(self, proposal: TradeProposal, state: RiskState) -> RiskDecisionRecord:
        now = datetime.now(timezone.utc)
        reasons: list[str] = []
        decision = RiskDecision.APPROVE
        qty = 0.0
        permitted = 0.0
        rr_after = None

        # Kill switch
        if self.kill_switch.is_halted():
            return RiskDecisionRecord(
                signal_id=proposal.signal_id,
                decision=RiskDecision.REJECT,
                reason_codes=[f"KILL_SWITCH_{self.kill_switch.level().value}"],
                calculated_quantity=0.0,
                risk_profile_version=self.profile_version,
                evaluated_at=now,
                decision_state=DecisionState.NO_TRADE,
            )

        # Event lock
        if proposal.event_lock_active:
            reasons.append("HIGH_IMPACT_EVENT_LOCK")

        # Concurrent positions
        if state.open_positions >= self.risk["max_concurrent_positions"]:
            reasons.append("MAX_CONCURRENT_POSITIONS")
        if state.positions_by_symbol.get(proposal.symbol, 0) >= self.risk["max_positions_per_symbol"]:
            reasons.append("MAX_POSITIONS_PER_SYMBOL")

        # Loss streak
        if state.loss_streak >= self.risk["max_loss_streak"]:
            reasons.append("MAX_LOSS_STREAK")

        # Daily loss
        max_daily_loss = state.equity * self.risk["max_daily_loss_pct"]
        remaining_daily = max_daily_loss + state.realized_pnl_today  # pnl negative when losing
        if state.realized_pnl_today <= -max_daily_loss:
            reasons.append("MAX_DAILY_LOSS")
            remaining_daily = 0.0

        # Spread
        if (
            proposal.spread is not None
            and proposal.median_spread is not None
            and proposal.median_spread > 0
            and proposal.spread > self.risk["max_spread_vs_median"] * proposal.median_spread
        ):
            reasons.append("MAX_SPREAD_EXCEEDED")

        # Stop vs ATR
        stop_dist = abs(proposal.entry - proposal.stop)
        if (
            proposal.atr_15m
            and proposal.atr_15m > 0
            and stop_dist > self.risk["max_stop_atr_multiple"] * proposal.atr_15m
        ):
            reasons.append("MAX_STOP_ATR")

        # Planned R:R
        if proposal.targets:
            reward = abs(proposal.targets[0] - proposal.entry)
            planned_rr = reward / stop_dist if stop_dist > 0 else 0.0
            # Rough cost buffer in price terms
            fee_bps = self.paper["fee_bps"]
            slip_bps = self.paper["slippage_bps"]
            cost_frac = (fee_bps + slip_bps) * 2 / 10_000.0  # round trip
            cost_price = proposal.entry * cost_frac
            rr_after = (reward - cost_price) / (stop_dist + cost_price) if (stop_dist + cost_price) > 0 else 0.0
            if rr_after < self.risk["min_planned_rr"]:
                reasons.append("MIN_RR_AFTER_COSTS")
        else:
            reasons.append("NO_TARGETS")

        # Evidence data quality
        if any(not e.data_quality_ok for e in proposal.evidence):
            reasons.append("DATA_QUALITY")

        # Sizing
        contract = float(self.paper["contract_value"].get(proposal.symbol, 1.0))
        fee_est = proposal.entry * contract * self.paper["fee_bps"] / 10_000.0
        slip_est = proposal.entry * contract * self.paper["slippage_bps"] / 10_000.0
        loss_per_unit = stop_dist * contract + fee_est + slip_est

        risk_budget = state.equity * self.risk["risk_per_trade_pct"]
        remaining_open = max(0.0, state.equity * self.risk["max_open_risk_pct"] - state.open_risk)
        permitted = min(risk_budget, max(0.0, remaining_daily), remaining_open)

        increment = float(self.paper["lot_increment"].get(proposal.symbol, 0.01))
        if loss_per_unit > 0 and permitted > 0:
            raw = permitted / loss_per_unit
            qty = math.floor(raw / increment) * increment
        else:
            qty = 0.0

        if qty <= 0 and "MAX_DAILY_LOSS" not in reasons and "KILL_SWITCH" not in "".join(reasons):
            reasons.append("QTY_ZERO")

        # Decision logic
        hard_rejects = {
            "HIGH_IMPACT_EVENT_LOCK",
            "MAX_CONCURRENT_POSITIONS",
            "MAX_POSITIONS_PER_SYMBOL",
            "MAX_LOSS_STREAK",
            "MAX_DAILY_LOSS",
            "DATA_QUALITY",
            "MAX_SPREAD_EXCEEDED",
            "NO_TARGETS",
        }
        if any(r in hard_rejects for r in reasons) or qty <= 0:
            decision = RiskDecision.REJECT
            decision_state = DecisionState.NO_TRADE
            qty = 0.0
        elif "MAX_STOP_ATR" in reasons or "MIN_RR_AFTER_COSTS" in reasons:
            # Attempt reduce: tighten conceptually by reducing size further — if still fail RR, reject
            reduced = math.floor((qty * 0.5) / increment) * increment if qty > 0 else 0.0
            if reduced > 0 and "MIN_RR_AFTER_COSTS" not in reasons:
                decision = RiskDecision.REDUCE_SIZE
                qty = reduced
                decision_state = DecisionState.PAPER_TRADE_APPROVED
                reasons.append("SIZE_REDUCED")
            elif "MIN_RR_AFTER_COSTS" in reasons:
                decision = RiskDecision.REJECT
                decision_state = DecisionState.NO_TRADE
                qty = 0.0
            else:
                decision = RiskDecision.DEFER
                decision_state = DecisionState.WAIT_FOR_CONFIRMATION
                qty = 0.0
        else:
            decision = RiskDecision.APPROVE
            decision_state = DecisionState.PAPER_TRADE_APPROVED

        return RiskDecisionRecord(
            signal_id=proposal.signal_id,
            decision=decision,
            reason_codes=reasons,
            calculated_quantity=round(float(qty), 8),
            permitted_risk=round(float(permitted), 8),
            planned_rr_after_costs=rr_after,
            risk_profile_version=self.profile_version,
            evaluated_at=now,
            decision_state=decision_state,
        )
