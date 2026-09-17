# Kill switch

**Authority:** Human owner can always fire it. Trading CEO may recommend or soft-halt for governance breaches. Clearing requires human owner confirmation.

## Levels

| Level | Effect |
|-------|--------|
| `SOFT_HALT` | No new entries; manage open paper positions per plan |
| `HARD_HALT` | No new entries; cancel working entries; flatten paper positions per policy |
| `FULL_LOCK` | Same as hard + block all config/strategy changes until review |

## Auto-triggers (paper-v1)

- Daily loss limit reached
- Loss streak limit reached
- Data freshness breach on active symbol
- Schema / risk-engine failure rate above threshold
- Manual owner or Trading CEO halt

## Requirements

- Lives outside LLM prompts and agent UIs
- Execution service polls / receives push and stops within one control cycle
- Every activation and clear is logged with timestamp, actor, reason
