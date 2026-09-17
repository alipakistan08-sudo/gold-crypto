from trading_desk.config import load_config
from trading_desk.pipeline import demonstrate_live_refusal, run_paper_session


def test_paper_session_journals_path():
    cfg = load_config()
    out = run_paper_session(cfg=cfg, seed=42)
    summary = out["journal_summary"]
    assert summary["total_records"] >= 1
    # At least one proposal or no-trade path
    counts = summary["counts"]
    assert counts.get("NO_TRADE", 0) + counts.get("PROPOSAL", 0) >= 1
    # If any proposal, risk decision must exist
    if counts.get("PROPOSAL", 0) > 0:
        assert counts.get("RISK_DECISION", 0) >= 1
        assert summary["signal_ids"]


def test_live_refusal_message():
    msg = demonstrate_live_refusal()
    assert "LIVE" in msg.upper()
    assert "REFUSED" in msg.upper() or "DISABLED" in msg.upper()
