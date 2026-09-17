"""Deterministic agent stubs — structured evidence only; no sizing or orders."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from trading_desk.data.bars import BarSeries
from trading_desk.features.indicators import FeatureSnapshot
from trading_desk.models.enums import DecisionState
from trading_desk.models.signal import AgentEvidence, TradeProposal
from trading_desk.setups.sweep_reclaim import SETUP_ID, SETUP_VERSION, SetupMatch, evaluate_sweep_reclaim


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MarketScout:
    name = "market_scout"

    def analyze(self, features: FeatureSnapshot, data_ok: bool) -> AgentEvidence:
        flags = []
        if not data_ok:
            flags.append("DATA_STALE")
        if features.vol_regime.value in ("HIGH", "EXTREME"):
            flags.append(f"VOL_{features.vol_regime.value}")
        move = abs(features.close - features.vwap) / features.close if features.close else 0
        if move > 0.004:
            flags.append("AWAY_FROM_VWAP")
        return AgentEvidence(
            agent=self.name,
            timestamp=features.ts,
            symbol=features.symbol,
            summary=f"session={features.session} regime={features.regime} vol={features.vol_regime.value}",
            flags=flags,
            metrics={"close": features.close, "vwap": features.vwap, "atr": features.atr},
            data_quality_ok=data_ok,
        )


class TechnicalAnalyst:
    name = "technical_analyst"

    def analyze(self, features: FeatureSnapshot, structure: BarSeries) -> AgentEvidence:
        flags = []
        if features.close > features.ema_fast > features.ema_slow:
            structure_label = "BULLISH_STACK"
        elif features.close < features.ema_fast < features.ema_slow:
            structure_label = "BEARISH_STACK"
            flags.append("BEARISH_STRUCTURE")
        else:
            structure_label = "MIXED"
            flags.append("MIXED_STRUCTURE")
        return AgentEvidence(
            agent=self.name,
            timestamp=features.ts,
            symbol=features.symbol,
            summary=f"structure={structure_label} swing_h={features.recent_swing_high:.4f} swing_l={features.recent_swing_low:.4f}",
            flags=flags,
            metrics={
                "ema_fast": features.ema_fast,
                "ema_slow": features.ema_slow,
                "structure": structure_label,
                "bars": len(structure.bars),
            },
            data_quality_ok=True,
        )


class LiquidityAgent:
    name = "liquidity_agent"

    def analyze(self, features: FeatureSnapshot, match: SetupMatch | None) -> AgentEvidence:
        flags = []
        spread_ratio = (
            features.spread_proxy / features.median_spread_proxy
            if features.median_spread_proxy > 0
            else 1.0
        )
        if spread_ratio > 2.0:
            flags.append("WIDE_SPREAD")
        if match and match.matched:
            flags.append(f"SWEEP_RECLAIM_{match.side.value if match.side else 'NA'}")
        return AgentEvidence(
            agent=self.name,
            timestamp=features.ts,
            symbol=features.symbol,
            summary=f"spread_ratio={spread_ratio:.2f} proxy={features.spread_proxy:.6f}",
            flags=flags,
            metrics={"spread_ratio": spread_ratio, "spread_proxy": features.spread_proxy},
            data_quality_ok=True,
        )


class MacroNewsAgent:
    name = "macro_news_agent"

    def analyze(
        self,
        features: FeatureSnapshot,
        event_lock_active: bool,
        crypto_event_flag: bool = False,
    ) -> AgentEvidence:
        flags = []
        if event_lock_active:
            flags.append("HIGH_IMPACT_EVENT_LOCK")
        if crypto_event_flag and features.symbol.endswith("/USDT"):
            flags.append("CRYPTO_EVENT_FLAG")
        return AgentEvidence(
            agent=self.name,
            timestamp=features.ts,
            symbol=features.symbol,
            summary="event_lock_active" if event_lock_active else "no active event lock",
            flags=flags,
            metrics={"event_lock_active": event_lock_active, "crypto_event_flag": crypto_event_flag},
            data_quality_ok=True,
        )


class SetupHunter:
    name = "setup_hunter"

    def synthesize(
        self,
        symbol: str,
        features: FeatureSnapshot,
        match: SetupMatch,
        evidence: list[AgentEvidence],
        venue: str = "paper-sim-v1",
        signal_seq: int = 1,
    ) -> TradeProposal | None:
        ts = features.ts if features.ts.tzinfo else features.ts.replace(tzinfo=timezone.utc)
        signal_id = f"{symbol.replace('/', '').lower()}-{ts.strftime('%Y-%m-%dT%H%M%SZ')}-{signal_seq:03d}"

        if not match.matched or match.side is None:
            # Explicit NO_TRADE proposal path via None; caller logs decision
            return None

        return TradeProposal(
            signal_id=signal_id,
            created_at=_now(),
            symbol=symbol,
            venue=venue,
            setup_id=SETUP_ID,
            setup_version=SETUP_VERSION,
            side=match.side,
            session=features.session,
            regime=features.regime,
            vol_regime=features.vol_regime.value,
            entry=float(match.entry),
            stop=float(match.stop),
            targets=list(match.targets),
            planned_rr=match.planned_rr,
            invalidation=match.invalidation,
            exclusions_checked=["EVENT_LOCK", "DATA_STALE", "EXTREME_VOL", "OFF_HOURS", "STOP_TOO_WIDE"],
            evidence=evidence,
            decision_state=DecisionState.WAIT_FOR_CONFIRMATION,
            quality_score=match.quality_score,
            notes=match.reason,
            spread=features.spread_proxy * features.close,
            atr_15m=features.atr,
            median_spread=features.median_spread_proxy * features.close,
            event_lock_active=any("EVENT_LOCK" in e.flags or "HIGH_IMPACT_EVENT_LOCK" in e.flags for e in evidence),
        )


def run_evidence_pipeline(
    symbol: str,
    features: FeatureSnapshot,
    structure: BarSeries,
    execution: BarSeries,
    data_ok: bool,
    event_lock_active: bool = False,
    crypto_event_flag: bool = False,
    venue: str = "paper-sim-v1",
    signal_seq: int = 1,
) -> tuple[list[AgentEvidence], SetupMatch, TradeProposal | None]:
    match = evaluate_sweep_reclaim(
        structure, execution, features, event_lock_active=event_lock_active, data_ok=data_ok
    )
    scout = MarketScout().analyze(features, data_ok)
    tech = TechnicalAnalyst().analyze(features, structure)
    liq = LiquidityAgent().analyze(features, match)
    macro = MacroNewsAgent().analyze(features, event_lock_active, crypto_event_flag)
    evidence = [scout, tech, liq, macro]
    proposal = SetupHunter().synthesize(symbol, features, match, evidence, venue=venue, signal_seq=signal_seq)
    return evidence, match, proposal
