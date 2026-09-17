from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from trading_desk.models.enums import Side
from trading_desk.models.signal import TradeProposal, validate_proposal


def test_valid_proposal():
    p = validate_proposal(
        {
            "signal_id": "xauusd-2026-09-17T093500Z-001",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "symbol": "XAU/USD",
            "setup_id": "sweep-reclaim",
            "setup_version": "sweep-reclaim-v1",
            "side": "LONG",
            "session": "LONDON",
            "regime": "TREND_UP",
            "vol_regime": "NORMAL",
            "entry": 2400.0,
            "stop": 2395.0,
            "targets": [2407.5, 2412.5],
            "planned_rr": 1.5,
            "invalidation": "below sweep",
        }
    )
    assert p.side == Side.LONG
    assert p.schema_version == "signal-v1"


def test_empty_targets_rejected():
    with pytest.raises(ValidationError):
        TradeProposal(
            signal_id="bad",
            created_at=datetime.now(timezone.utc),
            symbol="BTC/USDT",
            setup_id="sweep-reclaim",
            setup_version="sweep-reclaim-v1",
            side=Side.LONG,
            session="CRYPTO_24x7",
            regime="RANGE",
            vol_regime="NORMAL",
            entry=1.0,
            stop=0.9,
            targets=[],
            planned_rr=1.5,
            invalidation="x",
        )
