import pytest

from trading_desk.models.enums import KillLevel
from trading_desk.risk.kill_switch import KillSwitch


def test_activate_and_status(tmp_path):
    ks = KillSwitch(tmp_path / "kill.json")
    assert ks.level() == KillLevel.CLEAR
    ks.activate(KillLevel.SOFT_HALT, actor="owner", reason="daily review")
    assert ks.is_halted()
    assert ks.level() == KillLevel.SOFT_HALT


def test_clear_requires_owner(tmp_path):
    ks = KillSwitch(tmp_path / "kill.json")
    ks.activate(KillLevel.HARD_HALT, actor="ceo", reason="breach")
    with pytest.raises(PermissionError):
        ks.clear(actor="agent", reason="nope", owner_confirmed=False)
    ks.clear(actor="owner", reason="reviewed", owner_confirmed=True)
    assert ks.level() == KillLevel.CLEAR


def test_agents_cannot_use_clear_without_flag(tmp_path):
    ks = KillSwitch(tmp_path / "kill.json")
    ks.activate(KillLevel.FULL_LOCK, actor="owner", reason="lock")
    with pytest.raises(PermissionError):
        ks.clear("llm", "ignore")
