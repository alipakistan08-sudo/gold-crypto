# Operator charter — Phase 0

**Desk:** Gold and Crypto AI Intraday Trading Desk  
**Human owner:** Tanveer Ashraf  
**Governing role (AI):** Trading CEO  
**Status:** Draft pending owner approval  
**Effective:** paper-trading only until live is explicitly enabled  

## Accountability

| Role | Owns |
|------|------|
| Human owner | Risk capital, live activation, final limit numbers, broker/exchange credentials, regulatory compliance |
| Trading CEO | Day-to-day governance of the charter: setup versions, research promotion gates, session readiness, post-trade review discipline, veto of unsafe automation |
| Deterministic risk engine | Final size, APPROVE / REJECT / REDUCE / DEFER — never overruled by narrative confidence |
| LLM agents | Evidence and proposals only — no credentials, no size, no unreviewed orders |

## Non-negotiable controls

1. No order without a valid, versioned JSON signal.
2. No LLM-selected position size.
3. No new trade when data is stale, spread is excessive, or a high-impact event lockout is active.
4. No strategy change in a live session without change control and re-validation.
5. Kill switch disables new entries (and optionally flattens) independently of the AI layer.

## Decision states

`NO_TRADE` → `WAIT_FOR_CONFIRMATION` → `PAPER_TRADE_APPROVED` → `LIVE_TRADE_APPROVED`

`LIVE_TRADE_APPROVED` is unavailable until Phase 5 exit criteria are met and the human owner explicitly enables live execution.

## Scope at launch

**In:** XAU/USD, BTC/USDT, ETH/USDT; 1h regime / 15m structure / 5m execution; one or two predefined setups; paper execution + journal.

**Out until validated:** altcoins, discretionary news prediction, HFT, cross-exchange arb, autonomous portfolio rotation, live execution, unsupervised model changes.
