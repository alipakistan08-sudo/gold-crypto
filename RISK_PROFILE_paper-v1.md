# Risk profile — `paper-v1`

**Version:** paper-v1  
**Mode:** paper only  
**Owner approval required before any number change**

## Instruments allowed

| Symbol | Class | Sessions of interest | Notes |
|--------|-------|----------------------|-------|
| XAU/USD | Gold | London, New York | Strict event locks (CPI, PCE, NFP, FOMC) |
| BTC/USDT | Crypto | 24/7 | Funding / OI / venue health matter |
| ETH/USDT | Crypto | 24/7 | Same as BTC; treat separately in journal |

## Sizing (deterministic — never set by LLM)

```
permitted_risk = min(
  account_equity * risk_per_trade_pct,
  remaining_daily_loss_budget,
  remaining_group_exposure_budget
)
estimated_loss_per_unit = abs(entry - stop) * contract_value
                        + spread_cost + fees + slippage_buffer
quantity = floor_to_venue_increment(permitted_risk / estimated_loss_per_unit)
approve only when quantity > 0 and all hard limits pass
```

## Default limits (placeholders — owner must set real values)

| Parameter | Paper default | Live (later) |
|-----------|---------------|--------------|
| Risk per trade | 0.25% of equity | TBD by owner |
| Max daily loss | 1.0% of equity | TBD |
| Max open risk (all symbols) | 0.75% of equity | TBD |
| Max concurrent positions | 1 | TBD |
| Max positions per symbol | 1 | TBD |
| Max loss streak (halt new entries) | 3 | TBD |
| Min planned R:R after costs | 1.5R | TBD |
| Max stop distance (ATR multiple) | 2.0 × ATR(14, 15m) | TBD |
| Max spread vs typical | Reject if > 2× median session spread | Same idea |
| Data freshness SLA | Bars ≤ 2 intervals late; quotes ≤ 5s crypto / 10s gold | Same |

## Event locks

- **Gold:** high-impact US macro (CPI, PCE, NFP, FOMC) — no new entries from lock_start to lock_end (owner sets windows, e.g. −15m / +15m around print).
- **Crypto:** exchange outage, major network halt, or operator-flagged crypto event — no new entries while flag active.
- Macro lock always wins over technical confidence.

## Kill switch

See `KILL_SWITCH.md`. Risk engine and execution adapter must honor it immediately; agents cannot clear it.
