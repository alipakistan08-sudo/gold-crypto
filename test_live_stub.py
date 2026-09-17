import pytest

from trading_desk.config import load_config
from trading_desk.execution.live_stub import LiveExecutionAdapter, LiveGateError


def test_live_disabled_by_default():
    cfg = load_config()
    assert cfg["live"]["enabled"] is False
    adapter = LiveExecutionAdapter(cfg)
    with pytest.raises(LiveGateError) as ei:
        adapter.place()
    assert "LIVE_DISABLED" in str(ei.value)


def test_live_enabled_without_ack(tmp_path):
    cfg = load_config()
    cfg = dict(cfg)
    cfg["live"] = dict(cfg["live"])
    cfg["live"]["enabled"] = True
    cfg["live"]["owner_ack_path"] = str(tmp_path / "NO_ACK")
    adapter = LiveExecutionAdapter(cfg)
    with pytest.raises(LiveGateError) as ei:
        adapter.place()
    assert "OWNER_ACK_MISSING" in str(ei.value)


def test_live_with_gates_still_stub(tmp_path):
    cfg = load_config()
    cfg = dict(cfg)
    cfg["live"] = dict(cfg["live"])
    cfg["live"]["enabled"] = True
    ack = tmp_path / "ACK"
    ack.write_text("OWNER ACK")
    cfg["live"]["owner_ack_path"] = str(ack)
    adapter = LiveExecutionAdapter(cfg)
    with pytest.raises(LiveGateError) as ei:
        adapter.place()
    assert "stub" in str(ei.value).lower() or "credentials" in str(ei.value).lower()
