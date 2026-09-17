from datetime import datetime, timedelta, timezone

from trading_desk.data.bars import Bar
from trading_desk.data.freshness import check_bar_freshness, check_quote_freshness


def test_bar_fresh_ok():
    ts = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    bar = Bar("BTC/USDT", ts, 1, 1, 1, 1, 1, "5m")
    now = ts + timedelta(minutes=3)
    r = check_bar_freshness(bar, now, interval_minutes=5, max_intervals_late=2)
    assert r.ok


def test_bar_stale():
    ts = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    bar = Bar("BTC/USDT", ts, 1, 1, 1, 1, 1, "5m")
    now = ts + timedelta(minutes=5 + 2 * 5 + 1)  # past close + 2 intervals
    r = check_bar_freshness(bar, now, interval_minutes=5, max_intervals_late=2)
    assert not r.ok
    assert "STALE_BARS" in r.reason


def test_quote_freshness():
    now = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    ok = check_quote_freshness(now - timedelta(seconds=3), now, max_age_seconds=5)
    bad = check_quote_freshness(now - timedelta(seconds=12), now, max_age_seconds=5)
    assert ok.ok
    assert not bad.ok
