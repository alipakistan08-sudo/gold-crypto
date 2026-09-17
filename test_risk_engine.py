from datetime import datetime, timezone

from trading_desk.config import load_config
from trading_desk.models.enums import DecisionState, RiskDecision, Side
from trading_desk.models.signal import AgentEvidence, TradeProposal
from trading_desk.risk.engine import RiskEngine, RiskState
from trading_desk.risk.kill_switch import KillSwitch


def _proposal(**kwargs) -> TradeProposal:
    base = dict(
        signal_id="test-001",
        created_at=datetime.now(timezone.utc),
        symbol="BTC/USDT",
        setup_id="sweep-reclaim",
        setup_version="sweep-reclaim-v1",
        side=Side.LONG,
        session="CRYPTO_24x7",
        regime="TREND_UP",
        vol_regime="NORMAL",
        entry=65000.0,
        stop=64500.0,
        targets=[66250.0, 67000.0],
        planned_rr=2.5,
        invalidation="below sweep",
        evidence=[
            AgentEvidence(
                agent="market_scout",
                timestamp=datetime.now(timezone.utc),
                symbol="BTC/USDT",
                summary="ok",
                data_quality_ok=True,
            )
        ],
        decision_state=DecisionState.WAIT_FOR_CONFIRMATION,
        quality_score=0.8,
        spread=5.0,
        atr_15m=400.0,
        median_spread=4.0,
        event_lock_active=False,
    )
    base.update(kwargs)
    return TradeProposal(**base)


def test_approve_happy_path(tmp_path):
    cfg = load_config()
    ks = KillSwitch(tmp_path / "ks.json")
    engine = RiskEngine(cfg, ks)
    state = RiskState(equity=100_000.0)
    rec = engine.evaluate(_proposal(), state)
    assert rec.decision == RiskDecision.APPROVE
    assert rec.calculated_quantity > 0
    assert rec.decision_state == DecisionState.PAPER_TRADE_APPROVED


def test_reject_event_lock(tmp_path):
    cfg = load_config()
    ks = KillSwitch(tmp_path / "ks.json")
    engine = RiskEngine(cfg, ks)
    rec = engine.evaluate(_proposal(event_lock_active=True), RiskState(equity=100_000.0))
    assert rec.decision == RiskDecision.REJECT
    assert "HIGH_IMPACT_EVENT_LOCK" in rec.reason_codes


def test_reject_max_concurrent(tmp_path):
    cfg = load_config()
    ks = KillSwitch(tmp_path / "ks.json")
    engine = RiskEngine(cfg, ks)
    state = RiskState(equity=100_000.0, open_positions=1)
    rec = engine.evaluate(_proposal(), state)
    assert rec.decision == RiskDecision.REJECT
    assert "MAX_CONCURRENT_POSITIONS" in rec.reason_codes


def test_reject_min_rr(tmp_path):
    cfg = load_config()
    ks = KillSwitch(tmp_path / "ks.json")
    engine = RiskEngine(cfg, ks)
    # Tight target -> RR after costs < 1.5
    rec = engine.evaluate(
        _proposal(entry=100.0, stop=99.0, targets=[100.5], atr_15m=2.0, spread=0.01, median_spread=0.01),
        RiskState(equity=100_000.0),
    )
    assert rec.decision == RiskDecision.REJECT
    assert "MIN_RR_AFTER_COSTS" in rec.reason_codes


def test_kill_switch_blocks(tmp_path):
    cfg = load_config()
    ks = KillSwitch(tmp_path / "ks.json")
    from trading_desk.models.enums import KillLevel

    ks.activate(KillLevel.HARD_HALT, actor="owner", reason="test")
    engine = RiskEngine(cfg, ks)
    rec = engine.evaluate(_proposal(), RiskState(equity=100_000.0))
    assert rec.decision == RiskDecision.REJECT
    assert any(c.startswith("KILL_SWITCH") for c in rec.reason_codes)
