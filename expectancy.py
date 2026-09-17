"""Expectancy metrics in R after costs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass
class ExpectancyReport:
    n: int
    win_rate: float
    avg_win_r: float
    avg_loss_r: float
    expectancy_r: float
    profit_factor: float


def compute_expectancy(r_multiples: Sequence[float]) -> ExpectancyReport:
    xs = list(r_multiples)
    n = len(xs)
    if n == 0:
        return ExpectancyReport(0, 0.0, 0.0, 0.0, 0.0, 0.0)
    wins = [x for x in xs if x > 0]
    losses = [x for x in xs if x <= 0]
    win_rate = len(wins) / n
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    gross_win = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.0
    pf = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    return ExpectancyReport(n, win_rate, avg_win, avg_loss, expectancy, pf)
