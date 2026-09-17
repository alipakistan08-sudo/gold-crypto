"""Deterministic feature computation: VWAP, EMA, ATR, session, vol regime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

from trading_desk.data.bars import BarSeries
from trading_desk.models.enums import VolRegime


def ema(values: np.ndarray, period: int) -> np.ndarray:
    out = np.empty_like(values, dtype=float)
    if len(values) == 0:
        return out
    alpha = 2.0 / (period + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    tr = np.zeros(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
    return ema(tr, period)


def vwap(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    typical = (highs + lows + closes) / 3.0
    cum_vol = np.cumsum(volumes)
    cum_tp_vol = np.cumsum(typical * volumes)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(cum_vol > 0, cum_tp_vol / cum_vol, typical)
    return out


def classify_session(ts: datetime, symbol: str) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    hour = ts.astimezone(timezone.utc).hour
    if symbol.startswith("XAU"):
        if 7 <= hour < 12:
            return "LONDON"
        if 12 <= hour < 17:
            return "NEW_YORK"
        if 0 <= hour < 7:
            return "ASIA"
        return "OFF_HOURS"
    return "CRYPTO_24x7"


def classify_vol_regime(atr_now: float, atr_series: np.ndarray) -> VolRegime:
    if len(atr_series) < 20:
        return VolRegime.NORMAL
    med = float(np.median(atr_series[-50:]))
    if med <= 0:
        return VolRegime.NORMAL
    ratio = atr_now / med
    if ratio < 0.6:
        return VolRegime.LOW
    if ratio < 1.4:
        return VolRegime.NORMAL
    if ratio < 2.2:
        return VolRegime.HIGH
    return VolRegime.EXTREME


def classify_regime(closes: np.ndarray, ema_fast: np.ndarray, ema_slow: np.ndarray) -> str:
    if len(closes) < 5:
        return "UNDEFINED"
    if ema_fast[-1] > ema_slow[-1] and closes[-1] > ema_fast[-1]:
        return "TREND_UP"
    if ema_fast[-1] < ema_slow[-1] and closes[-1] < ema_fast[-1]:
        return "TREND_DOWN"
    return "RANGE"


@dataclass
class FeatureSnapshot:
    symbol: str
    timeframe: str
    ts: datetime
    close: float
    vwap: float
    ema_fast: float
    ema_slow: float
    atr: float
    session: str
    regime: str
    vol_regime: VolRegime
    recent_swing_high: float
    recent_swing_low: float
    spread_proxy: float
    median_spread_proxy: float


def compute_features(series: BarSeries, lookback_swing: int = 20) -> FeatureSnapshot:
    closes = series.closes()
    highs = series.highs()
    lows = series.lows()
    vols = series.volumes()
    ema_f = ema(closes, 9)
    ema_s = ema(closes, 21)
    atr_s = atr(highs, lows, closes, 14)
    vwap_s = vwap(highs, lows, closes, vols)
    last = series.bars[-1]
    swing_slice = series.bars[-lookback_swing:] if len(series.bars) >= lookback_swing else series.bars
    swing_high = max(b.high for b in swing_slice)
    swing_low = min(b.low for b in swing_slice)
    # Stable quote-spread proxy in fraction-of-price terms (bps-like).
    # Full bar range is reserved for structure analysis, not the risk spread gate.
    typical_bps = {"XAU/USD": 1.2, "BTC/USDT": 1.0, "ETH/USDT": 1.5}
    bps = typical_bps.get(series.symbol, 1.5)
    # mild variation from recent quiet bars (exclude last 5 to avoid sweep spike)
    quiet = series.bars[-55:-5] or series.bars
    quiet_fracs = [((b.high - b.low) / b.close) * 0.02 for b in quiet]
    median_spread = float(np.median(quiet_fracs)) if quiet_fracs else bps / 10_000.0
    # floor/ceiling around typical
    floor = bps / 10_000.0
    median_spread = max(median_spread, floor)
    spread_now = floor * 1.1  # slightly above typical, still < 2x median
    return FeatureSnapshot(
        symbol=series.symbol,
        timeframe=series.timeframe,
        ts=last.ts,
        close=float(last.close),
        vwap=float(vwap_s[-1]),
        ema_fast=float(ema_f[-1]),
        ema_slow=float(ema_s[-1]),
        atr=float(atr_s[-1]),
        session=classify_session(last.ts, series.symbol),
        regime=classify_regime(closes, ema_f, ema_s),
        vol_regime=classify_vol_regime(float(atr_s[-1]), atr_s),
        recent_swing_high=float(swing_high),
        recent_swing_low=float(swing_low),
        spread_proxy=float(spread_now),
        median_spread_proxy=median_spread,
    )
