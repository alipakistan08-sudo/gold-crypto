# Phase 6 — Controlled Live Gate (LOCKED)

Live execution is **disabled by default**. The live adapter stub **fails closed**.

## Hard gates (all required)

1. [ ] Phases 0–5 exit criteria satisfied (paper sample, expectancy review, ops audit)
2. [ ] Human owner (Tanveer Ashraf) explicitly sets `live.enabled: true` in `config/desk.yaml`
3. [ ] Owner acknowledgment file exists at path configured by `live.owner_ack_path` (default `artifacts/LIVE_OWNER_ACK`)
4. [ ] Risk profile live numbers approved (not paper placeholders)
5. [ ] Kill switch tested (SOFT/HARD/FULL) with owner clear procedure
6. [ ] Broker/exchange credentials stored **outside** agent/LLM layer; never in prompts or agent tools
7. [ ] Tiny fixed risk for pilot; continuous monitoring; no unsupervised strategy changes

## Owner ack file format

Create a plain text file, e.g.:

```
OWNER: Tanveer Ashraf
ACK: I authorize limited live pilot under Phase 6 checklist.
DATE: YYYY-MM-DD (Europe/Rome)
```

## Adapter behavior

| Condition | Result |
|-----------|--------|
| `live.enabled=false` (default) | `LiveGateError: LIVE_DISABLED` |
| enabled but ack file missing | `LiveGateError: OWNER_ACK_MISSING` |
| both present | Still refuses — stub has **no** broker credentials; live implementation is future work |

## CLI check

```bash
python -m trading_desk.cli live-check
```

Must print a refusal and exit 0 (refusal is success for the gate test).

## Decision state

`LIVE_TRADE_APPROVED` remains unavailable until this checklist is complete and a real execution adapter is implemented under change control.
