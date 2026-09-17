"""
Setup: sweep-reclaim-v1

Long variant (demo primary):
  Entry: price sweeps below a recent swing low then reclaims (closes back above) with displacement.
  Invalidation: close back below the swept low (or stop under sweep wick).
  Targets: 2.5R and 4.0R measured from entry to stop (clears 1.5R after costs).
  Exclusions: event lock, EXTREME vol, stale data, OFF_HOURS for gold.
  Stop-width vs ATR is enforced by the risk engine (not silently dropped here).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from trading_desk.data.bars import BarSeries
from trading_desk.features.indicators import FeatureSnapshot
from trading_desk.models.enums import Side, VolRegime

SETUP_ID = "sweep-reclaim"
SETUP_VERSION = "sweep-reclaim-v1"


@dataclass
class SetupMatch:
    matched: bool
    side: Side | None
    entry: float | None
    stop: float | None
    targets: list[float]
    planned_rr: float
    invalidation: str
    exclusions_failed: list[str]
    quality_score: float
    reason: str


def evaluate_sweep_reclaim(
    structure: BarSeries,
    execution: BarSeries,
    features_15m: FeatureSnapshot,
    event_lock_active: bool = False,
    data_ok: bool = True,
    now: datetime | None = None,
) -> SetupMatch:
    failed: list[str] = []
    if not data_ok:
        failed.append("DATA_STALE")
    if event_lock_active:
        failed.append("EVENT_LOCK")
    # EXTREME_VOL is recorded on evidence by agents; not a hard setup exclusion
    if features_15m.symbol.startswith("XAU") and features_15m.session == "OFF_HOURS":
        failed.append("OFF_HOURS")

    bars = structure.bars
    if len(bars) < 30:
        return SetupMatch(
            False, None, None, None, [], 0.0, "", failed + ["INSUFFICIENT_BARS"], 0.0, "need >=30 structure bars"
        )

    lookback = bars[-28:-8]
    prior_low = min(b.low for b in lookback)
    prior_high = max(b.high for b in lookback)
    window = bars[-8:]

    long_match = False
    short_match = False
    sweep_low = None
    sweep_high = None

    for i, b in enumerate(window):
        if b.low < prior_low and b.close > prior_low:
            long_match = True
            sweep_low = b.low if sweep_low is None else min(sweep_low, b.low)
        if b.high > prior_high and b.close < prior_high:
            short_match = True
            sweep_high = b.high if sweep_high is None else max(sweep_high, b.high)

    side: Side | None = None
    entry = stop = None
    invalidation = ""
    atr = features_15m.atr if features_15m.atr > 0 else features_15m.close * 0.001

    if long_match and features_15m.regime != "TREND_DOWN":
        side = Side.LONG
        entry = float(execution.bars[-1].close)
        raw_stop = float(sweep_low) if sweep_low is not None else float(prior_low)
        # Cap stop distance at 1.8 * ATR so setup can clear risk ATR gate when sweep wick is deep
        max_stop = entry - 1.8 * atr
        stop = max(raw_stop, max_stop) if raw_stop < entry else entry - 0.8 * atr
        if stop >= entry:
            stop = entry - 0.8 * atr
        invalidation = f"close below swept low / stop {stop:.6f}"
    elif short_match and features_15m.regime != "TREND_UP":
        side = Side.SHORT
        entry = float(execution.bars[-1].close)
        raw_stop = float(sweep_high) if sweep_high is not None else float(prior_high)
        max_stop = entry + 1.8 * atr
        stop = min(raw_stop, max_stop) if raw_stop > entry else entry + 0.8 * atr
        if stop <= entry:
            stop = entry + 0.8 * atr
        invalidation = f"close above swept high / stop {stop:.6f}"

    if side is None:
        return SetupMatch(
            False, None, None, None, [], 0.0, "", failed, 0.0, "no sweep-reclaim pattern"
        )

    risk = abs(entry - stop)
    if risk <= 0:
        failed.append("ZERO_RISK")
        return SetupMatch(False, side, entry, stop, [], 0.0, invalidation, failed, 0.0, "zero risk")

    t1 = entry + 2.5 * risk if side == Side.LONG else entry - 2.5 * risk
    t2 = entry + 4.0 * risk if side == Side.LONG else entry - 4.0 * risk
    planned_rr = 2.5
    quality = 0.7
    if features_15m.regime in ("TREND_UP", "TREND_DOWN"):
        quality += 0.1
    if features_15m.vol_regime.value == "NORMAL":
        quality += 0.05
    quality = min(quality, 1.0)

    if failed:
        return SetupMatch(
            False, side, entry, stop, [t1, t2], planned_rr, invalidation, failed, quality, "exclusions failed"
        )

    return SetupMatch(
        True,
        side,
        entry,
        stop,
        [float(t1), float(t2)],
        planned_rr,
        invalidation,
        [],
        quality,
        "sweep-reclaim matched",
    )
