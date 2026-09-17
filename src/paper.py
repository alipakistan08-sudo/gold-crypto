"""Paper venue paper-sim-v1 — simulated fills with fees and slippage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from trading_desk.models.enums import Side
from trading_desk.models.signal import RiskDecisionRecord, TradeProposal


@dataclass
class PaperFill:
    signal_id: str
    symbol: str
    side: str
    quantity: float
    fill_price: float
    fee: float
    slippage: float
    venue: str
    filled_at: datetime
    client_order_id: str


class PaperSimVenue:
    venue_id = "paper-sim-v1"

    def __init__(self, cfg: dict[str, Any]):
        self.fee_bps = float(cfg["paper"]["fee_bps"])
        self.slippage_bps = float(cfg["paper"]["slippage_bps"])

    def place(
        self,
        proposal: TradeProposal,
        risk: RiskDecisionRecord,
    ) -> PaperFill:
        if risk.calculated_quantity <= 0:
            raise ValueError("cannot place with zero quantity")
        if risk.decision.value not in ("APPROVE", "REDUCE_SIZE"):
            raise ValueError(f"cannot place on decision={risk.decision}")

        slip = proposal.entry * self.slippage_bps / 10_000.0
        if proposal.side == Side.LONG:
            fill_price = proposal.entry + slip
        else:
            fill_price = proposal.entry - slip
        fee = fill_price * risk.calculated_quantity * self.fee_bps / 10_000.0
        now = datetime.now(timezone.utc)
        return PaperFill(
            signal_id=proposal.signal_id,
            symbol=proposal.symbol,
            side=proposal.side.value,
            quantity=risk.calculated_quantity,
            fill_price=fill_price,
            fee=fee,
            slippage=slip * risk.calculated_quantity,
            venue=self.venue_id,
            filled_at=now,
            client_order_id=f"{self.venue_id}:{proposal.signal_id}",
        )
