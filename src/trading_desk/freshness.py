"""Data freshness checks (bars + quotes)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .bars import Bar


@dataclass(frozen=True)
class FreshnessResult:
    ok: bool
    reason: str
    age_seconds: float | None = None


def _ensure_aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def check_bar_freshness(
    last_bar: Bar,
    now: datetime,
    interval_minutes: int,
    max_intervals_late: int = 2,
) -> FreshnessResult:
    now = _ensure_aware(now)
    last_ts = _ensure_aware(last_bar.ts)
    # Bar timestamp is open time; expected freshness window ends at close + grace
    expected_latest = last_ts.timestamp() + interval_minutes * 60
    age = now.timestamp() - expected_latest
    max_age = max_intervals_late * interval_minutes * 60
    if age > max_age:
        return FreshnessResult(
            ok=False,
            reason=f"STALE_BARS age={age:.0f}s max={max_age}s",
            age_seconds=age,
        )
    return FreshnessResult(ok=True, reason="OK", age_seconds=max(0.0, age))


def check_quote_freshness(
    quote_ts: datetime,
    now: datetime,
    max_age_seconds: float,
) -> FreshnessResult:
    now = _ensure_aware(now)
    quote_ts = _ensure_aware(quote_ts)
    age = (now - quote_ts).total_seconds()
    if age > max_age_seconds:
        return FreshnessResult(
            ok=False,
            reason=f"STALE_QUOTE age={age:.1f}s max={max_age_seconds}s",
            age_seconds=age,
        )
    return FreshnessResult(ok=True, reason="OK", age_seconds=age)


def is_crypto(symbol: str) -> bool:
    return symbol.endswith("/USDT") or symbol in ("BTC/USDT", "ETH/USDT")
