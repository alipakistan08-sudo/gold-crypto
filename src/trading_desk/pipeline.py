"""End-to-end paper session orchestration."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trading_desk.agents.stubs import run_evidence_pipeline
from trading_desk.config import ensure_artifact_dirs, load_config
from trading_desk.data.bars import generate_synthetic_bars, save_bars_csv
from trading_desk.data.freshness import check_bar_freshness
from trading_desk.execution.live_stub import LiveExecutionAdapter
from trading_desk.execution.paper import PaperSimVenue
from trading_desk.features.indicators import compute_features
from trading_desk.journal.store import JournalStore
from trading_desk.models.enums import DecisionState, RiskDecision
from trading_desk.risk.engine import RiskEngine, RiskState
from trading_desk.risk.kill_switch import KillSwitch


def _tf_minutes(tf: str) -> int:
    return {"1m": 1, "5m": 5, "15m": 15, "1h": 60}[tf]


def run_paper_session(
    cfg: dict[str, Any] | None = None,
    symbols: list[str] | None = None,
    seed: int = 42,
    event_lock: bool = False,
    force_stale: bool = False,
    try_live: bool = False,
) -> dict[str, Any]:
    cfg = cfg or load_config()
    ensure_artifact_dirs(cfg)
    symbols = symbols or list(cfg["desk"]["symbols"])
    journal = JournalStore(cfg["paths"]["journal_dir"])
    # Fresh journal for demo clarity
    if journal.path.exists():
        journal.path.write_text("")

    kill = KillSwitch(cfg["kill_switch"]["path"])
    # Ensure clear for demo unless already halted by operator
    if kill.level().value != "CLEAR":
        pass  # honor existing halt

    risk_engine = RiskEngine(cfg, kill)
    paper = PaperSimVenue(cfg)
    state = RiskState(equity=float(cfg["account"]["equity"]))
    signal_dir = Path(cfg["paths"]["signal_dir"])
    replay_dir = Path(cfg["paths"]["replay_dir"])

    results: list[dict[str, Any]] = []
    seq = 1

    for symbol in symbols:
        # Multi-timeframe synthetic data
        bars_1h = generate_synthetic_bars(symbol, "1h", n=80, seed=seed, inject_sweep_reclaim=False)
        bars_15m = generate_synthetic_bars(symbol, "15m", n=120, seed=seed, inject_sweep_reclaim=True)
        bars_5m = generate_synthetic_bars(symbol, "5m", n=200, seed=seed, inject_sweep_reclaim=True)

        save_bars_csv(bars_15m, replay_dir / f"{symbol.replace('/', '_')}_15m.csv")
        save_bars_csv(bars_5m, replay_dir / f"{symbol.replace('/', '_')}_5m.csv")

        features = compute_features(bars_15m)
        # Freshness: use last bar time as "now" for replay (fresh), or far future if force_stale
        if force_stale:
            now = datetime.now(timezone.utc)
        else:
            now = bars_5m.bars[-1].ts
            # small epsilon after bar open so freshness OK
            from datetime import timedelta

            now = now + timedelta(minutes=1)

        fresh = check_bar_freshness(
            bars_5m.bars[-1],
            now,
            interval_minutes=_tf_minutes("5m"),
            max_intervals_late=cfg["risk"]["data_freshness"]["max_bar_intervals_late"],
        )
        data_ok = fresh.ok

        evidence, match, proposal = run_evidence_pipeline(
            symbol=symbol,
            features=features,
            structure=bars_15m,
            execution=bars_5m,
            data_ok=data_ok,
            event_lock_active=event_lock and symbol.startswith("XAU"),
            venue=cfg["desk"]["paper_venue"],
            signal_seq=seq,
        )
        seq += 1

        if proposal is None:
            journal.log_no_trade(
                symbol=symbol,
                reason="NO_SETUP_OR_EXCLUSION",
                evidence=evidence,
                match_reason=match.reason + (("|" + ",".join(match.exclusions_failed)) if match.exclusions_failed else ""),
            )
            results.append(
                {
                    "symbol": symbol,
                    "path": "NO_TRADE",
                    "match_reason": match.reason,
                    "exclusions": match.exclusions_failed,
                    "freshness": fresh.reason,
                }
            )
            continue

        # Persist versioned signal JSON
        signal_path = signal_dir / f"{proposal.signal_id}.json"
        signal_path.write_text(proposal.model_dump_json(indent=2))
        journal.log_proposal(proposal)

        risk_rec = risk_engine.evaluate(proposal, state)
        journal.log_risk(risk_rec)

        fill_info = None
        if risk_rec.decision in (RiskDecision.APPROVE, RiskDecision.REDUCE_SIZE) and risk_rec.calculated_quantity > 0:
            fill = paper.place(proposal, risk_rec)
            journal.log_fill(fill)
            state.open_positions += 1
            state.positions_by_symbol[symbol] = state.positions_by_symbol.get(symbol, 0) + 1
            state.open_risk += risk_rec.permitted_risk
            fill_info = {
                "quantity": fill.quantity,
                "fill_price": fill.fill_price,
                "fee": fill.fee,
                "client_order_id": fill.client_order_id,
            }
            # Demo: only one concurrent — subsequent symbols will REJECT
            proposal.decision_state = DecisionState.PAPER_TRADE_APPROVED
        else:
            proposal.decision_state = DecisionState.NO_TRADE

        # Optional live attempt (should fail closed)
        live_error = None
        if try_live:
            live = LiveExecutionAdapter(cfg)
            try:
                live.place(proposal, risk_rec)
            except Exception as e:
                live_error = str(e)

        results.append(
            {
                "symbol": symbol,
                "path": risk_rec.decision_state.value,
                "signal_id": proposal.signal_id,
                "risk_decision": risk_rec.decision.value,
                "reason_codes": risk_rec.reason_codes,
                "quantity": risk_rec.calculated_quantity,
                "fill": fill_info,
                "freshness": fresh.reason,
                "live_error": live_error,
                "signal_path": str(signal_path),
            }
        )

    summary = journal.summary()
    return {
        "results": results,
        "journal_summary": summary,
        "account_equity": state.equity,
        "open_positions": state.open_positions,
        "kill_switch": kill.status(),
    }


def demonstrate_live_refusal(cfg: dict[str, Any] | None = None) -> str:
    cfg = cfg or load_config()
    live = LiveExecutionAdapter(cfg)
    try:
        live.place()
        return "UNEXPECTED: live place succeeded"
    except Exception as e:
        return str(e)
