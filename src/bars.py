"""Synthetic + replayable OHLCV bars."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Bar:
    symbol: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str


@dataclass
class BarSeries:
    symbol: str
    timeframe: str
    bars: list[Bar]

    def closes(self) -> np.ndarray:
        return np.array([b.close for b in self.bars], dtype=float)

    def highs(self) -> np.ndarray:
        return np.array([b.high for b in self.bars], dtype=float)

    def lows(self) -> np.ndarray:
        return np.array([b.low for b in self.bars], dtype=float)

    def volumes(self) -> np.ndarray:
        return np.array([b.volume for b in self.bars], dtype=float)

    def timestamps(self) -> list[datetime]:
        return [b.ts for b in self.bars]


_BASE_PRICES = {
    "XAU/USD": 2400.0,
    "BTC/USDT": 65000.0,
    "ETH/USDT": 3400.0,
}

_VOL = {
    "XAU/USD": 0.0008,
    "BTC/USDT": 0.0025,
    "ETH/USDT": 0.0030,
}


def _tf_minutes(tf: str) -> int:
    mapping = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}
    if tf not in mapping:
        raise ValueError(f"unsupported timeframe: {tf}")
    return mapping[tf]


def generate_synthetic_bars(
    symbol: str,
    timeframe: str,
    n: int = 300,
    seed: int = 42,
    start: datetime | None = None,
    inject_sweep_reclaim: bool = True,
) -> BarSeries:
    """Generate replayable synthetic bars; optionally embed a sweep-reclaim pattern near the end."""
    rng = np.random.default_rng(seed + hash(symbol + timeframe) % 10_000)
    base = _BASE_PRICES[symbol]
    vol = _VOL[symbol]
    minutes = _tf_minutes(timeframe)
    if start is None:
        start = datetime(2026, 9, 17, 8, 0, tzinfo=timezone.utc)

    rets = rng.normal(0.0, vol, size=n)
    # Mild upward drift for demo predictability on structure TF
    if timeframe == "15m":
        rets = rets + 0.00015

    prices = base * np.cumprod(1.0 + rets)
    bars: list[Bar] = []
    for i, px in enumerate(prices):
        ts = start + timedelta(minutes=minutes * i)
        wick = abs(rng.normal(0, vol * px * 0.5))
        o = prices[i - 1] if i else px
        h = max(o, px) + wick
        l = min(o, px) - wick
        v = float(rng.uniform(80, 400) * (1.5 if timeframe == "5m" else 1.0))
        bars.append(Bar(symbol, ts, float(o), float(h), float(l), float(px), v, timeframe))

    if inject_sweep_reclaim and timeframe in ("5m", "15m") and n >= 40:
        # Embed a long sweep-reclaim in the last 8 structure bars:
        # lookback window used by setup is bars[-28:-8]; sweep window is bars[-8:]
        idx = n - 5
        recent_low = min(b.low for b in bars[idx - 20 : idx])
        sweep_bar = bars[idx]
        swept_low = recent_low - vol * base * 3
        reclaim_close = recent_low + vol * base * 0.5
        bars[idx] = Bar(
            symbol,
            sweep_bar.ts,
            float(recent_low + vol * base),
            max(float(sweep_bar.high), float(recent_low)),
            float(swept_low),
            float(reclaim_close),
            sweep_bar.volume * 2.5,
            timeframe,
        )
        # Displacement follow-through above reclaim
        px = reclaim_close
        for j in range(1, 5):
            if idx + j >= n:
                break
            b = bars[idx + j]
            px = px * (1.0 + vol * 2.0)
            bars[idx + j] = Bar(
                symbol,
                b.ts,
                float(b.open),
                max(float(b.high), float(px)),
                min(float(b.low), float(reclaim_close)),
                float(px),
                b.volume * 1.3,
                timeframe,
            )

    return BarSeries(symbol=symbol, timeframe=timeframe, bars=bars)


def save_bars_csv(series: BarSeries, path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "ts", "open", "high", "low", "close", "volume", "timeframe"])
        for b in series.bars:
            w.writerow(
                [
                    b.symbol,
                    b.ts.isoformat(),
                    b.open,
                    b.high,
                    b.low,
                    b.close,
                    b.volume,
                    b.timeframe,
                ]
            )


def load_bars_csv(path: Path | str) -> BarSeries:
    path = Path(path)
    bars: list[Bar] = []
    with path.open() as f:
        r = csv.DictReader(f)
        for row in r:
            bars.append(
                Bar(
                    symbol=row["symbol"],
                    ts=datetime.fromisoformat(row["ts"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                    timeframe=row["timeframe"],
                )
            )
    if not bars:
        raise ValueError(f"no bars in {path}")
    return BarSeries(symbol=bars[0].symbol, timeframe=bars[0].timeframe, bars=bars)
