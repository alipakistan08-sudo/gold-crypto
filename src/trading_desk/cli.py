"""CLI for paper demo, live gate check, and journal summary."""

from __future__ import annotations

import argparse
import json
import sys

from trading_desk.config import load_config
from trading_desk.journal.store import JournalStore
from trading_desk.metrics.expectancy import compute_expectancy
from trading_desk.pipeline import demonstrate_live_refusal, run_paper_session


def cmd_paper(args: argparse.Namespace) -> int:
    cfg = load_config(args.config) if args.config else load_config()
    out = run_paper_session(
        cfg=cfg,
        symbols=args.symbols.split(",") if args.symbols else None,
        seed=args.seed,
        event_lock=args.event_lock,
        force_stale=args.force_stale,
        try_live=args.try_live,
    )
    print("=== Paper Session Results ===")
    for r in out["results"]:
        print(json.dumps(r, indent=2, default=str))
        print("---")
    print("=== Journal Summary ===")
    print(json.dumps(out["journal_summary"], indent=2))
    print(f"Open positions: {out['open_positions']}")
    print(f"Kill switch: {out['kill_switch']['level']}")
    return 0


def cmd_journal(args: argparse.Namespace) -> int:
    cfg = load_config(args.config) if args.config else load_config()
    store = JournalStore(cfg["paths"]["journal_dir"])
    print(json.dumps(store.summary(), indent=2))
    if args.full:
        print("=== Records ===")
        for row in store.read_all():
            print(json.dumps(row, indent=2, default=str))
    return 0


def cmd_live_check(args: argparse.Namespace) -> int:
    cfg = load_config(args.config) if args.config else load_config()
    msg = demonstrate_live_refusal(cfg)
    print(msg)
    # Non-zero if somehow succeeded without gates (should not happen)
    if msg.startswith("UNEXPECTED"):
        return 2
    print("OK: live path failed closed as required.")
    return 0


def cmd_expectancy(args: argparse.Namespace) -> int:
    # Demo numbers or CLI-provided R multiples
    if args.r:
        rs = [float(x) for x in args.r.split(",")]
    else:
        rs = [1.5, -1.0, 2.0, -1.0, 1.8]
    report = compute_expectancy(rs)
    print(json.dumps(report.__dict__, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trading-desk", description="Gold/Crypto AI Intraday Trading Desk")
    parser.add_argument("--config", default=None, help="Path to desk.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_paper = sub.add_parser("paper", help="Run paper session on synthetic replayable data")
    p_paper.add_argument("--symbols", default=None, help="Comma-separated symbols")
    p_paper.add_argument("--seed", type=int, default=42)
    p_paper.add_argument("--event-lock", action="store_true")
    p_paper.add_argument("--force-stale", action="store_true")
    p_paper.add_argument("--try-live", action="store_true", help="Also attempt live stub (expects refusal)")
    p_paper.set_defaults(func=cmd_paper)

    p_j = sub.add_parser("journal", help="Show journal summary")
    p_j.add_argument("--full", action="store_true")
    p_j.set_defaults(func=cmd_journal)

    p_live = sub.add_parser("live-check", help="Verify live path fails closed")
    p_live.set_defaults(func=cmd_live_check)

    p_exp = sub.add_parser("expectancy", help="Compute expectancy from R multiples")
    p_exp.add_argument("--r", default=None, help="Comma-separated R multiples")
    p_exp.set_defaults(func=cmd_expectancy)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
