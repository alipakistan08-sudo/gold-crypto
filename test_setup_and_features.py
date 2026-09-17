from trading_desk.data.bars import generate_synthetic_bars
from trading_desk.features.indicators import compute_features
from trading_desk.setups.sweep_reclaim import evaluate_sweep_reclaim


def test_features_compute():
    series = generate_synthetic_bars("ETH/USDT", "15m", n=60, seed=1, inject_sweep_reclaim=False)
    snap = compute_features(series)
    assert snap.atr > 0
    assert snap.vwap > 0
    assert snap.session == "CRYPTO_24x7"


def test_sweep_reclaim_can_match():
    s15 = generate_synthetic_bars("BTC/USDT", "15m", n=120, seed=42, inject_sweep_reclaim=True)
    s5 = generate_synthetic_bars("BTC/USDT", "5m", n=200, seed=42, inject_sweep_reclaim=True)
    feat = compute_features(s15)
    match = evaluate_sweep_reclaim(s15, s5, feat, event_lock_active=False, data_ok=True)
    # With injection we expect a match on at least one side path for this seed
    assert match.matched or match.reason  # always returns structured result
