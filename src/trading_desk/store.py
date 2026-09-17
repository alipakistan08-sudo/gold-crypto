"""Append-only JSONL journal for proposals, risk decisions, fills, and no-trades."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trading_desk.execution.paper import PaperFill
from trading_desk.models.signal import RiskDecisionRecord, TradeProposal


class JournalStore:
    def __init__(self, directory: Path | str):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "journal.jsonl"

    def _append(self, record: dict[str, Any]) -> None:
        record.setdefault("logged_at", datetime.now(timezone.utc).isoformat())
        with self.path.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def log_no_trade(
        self,
        symbol: str,
        reason: str,
        evidence: list[Any] | None = None,
        match_reason: str = "",
        signal_id: str | None = None,
    ) -> None:
        self._append(
            {
                "type": "NO_TRADE",
                "symbol": symbol,
                "reason": reason,
                "match_reason": match_reason,
                "signal_id": signal_id,
                "evidence": [e.model_dump(mode="json") if hasattr(e, "model_dump") else e for e in (evidence or [])],
            }
        )

    def log_proposal(self, proposal: TradeProposal) -> None:
        self._append({"type": "PROPOSAL", "payload": proposal.model_dump(mode="json")})

    def log_risk(self, risk: RiskDecisionRecord) -> None:
        self._append({"type": "RISK_DECISION", "payload": risk.model_dump(mode="json")})

    def log_fill(self, fill: PaperFill) -> None:
        self._append(
            {
                "type": "FILL",
                "payload": {
                    "signal_id": fill.signal_id,
                    "symbol": fill.symbol,
                    "side": fill.side,
                    "quantity": fill.quantity,
                    "fill_price": fill.fill_price,
                    "fee": fill.fee,
                    "slippage": fill.slippage,
                    "venue": fill.venue,
                    "filled_at": fill.filled_at.isoformat(),
                    "client_order_id": fill.client_order_id,
                },
            }
        )

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = []
        with self.path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def summary(self) -> dict[str, Any]:
        rows = self.read_all()
        counts = {"NO_TRADE": 0, "PROPOSAL": 0, "RISK_DECISION": 0, "FILL": 0}
        decisions: dict[str, int] = {}
        signal_ids: list[str] = []
        for r in rows:
            t = r.get("type", "")
            counts[t] = counts.get(t, 0) + 1
            if t == "RISK_DECISION":
                d = r["payload"]["decision"]
                decisions[d] = decisions.get(d, 0) + 1
                signal_ids.append(r["payload"]["signal_id"])
            elif t == "PROPOSAL":
                signal_ids.append(r["payload"]["signal_id"])
            elif t == "NO_TRADE" and r.get("signal_id"):
                signal_ids.append(r["signal_id"])
        return {
            "total_records": len(rows),
            "counts": counts,
            "risk_decisions": decisions,
            "signal_ids": signal_ids,
            "path": str(self.path),
        }
