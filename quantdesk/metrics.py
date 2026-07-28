"""Forward-evaluation metrics — the numbers the promotion gate actually reads.

Everything here is deliberately *forward*: it scores decisions that were
committed to a ledger **before** the outcome was known. Nothing in this module
can be run over a backtest and passed off as evidence, because every function
takes a settled ledger row — a probability that was stamped at decision time,
the price that was available then, and what actually happened.

Four numbers matter, and they answer four different questions:

    brier_skill  — is the model better than the market?      (skill <= 0 = no)
    ece          — when it says 70%, does it happen 70%?     (calibration)
    clv_bps      — did the price move our way after we acted? (execution edge)
    paper_pnl    — after fees, did it make money?             (the only real one)

A strategy has to clear all four to advance. Most don't. That is the point:
these functions exist to *kill* strategies, and over the run they killed 14.

Pure standard library — no numpy, no scipy. The bootstrap is written out
longhand because the clustering is the subtle part, and a reader should be
able to check it.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Iterable, Sequence

__all__ = [
    "brier",
    "brier_skill",
    "ece",
    "reliability_table",
    "clv_bps",
    "clustered_bootstrap_ci",
    "log_loss",
]


# --------------------------------------------------------------------------
# Accuracy of a probability
# --------------------------------------------------------------------------


def brier(probs: Sequence[float], outcomes: Sequence[int]) -> float:
    """Mean squared error of a probabilistic forecast. Lower is better.

    A coin-flip forecaster scores 0.25. A forecaster that is always right and
    always certain scores 0.0.
    """
    _check_pairs(probs, outcomes)
    return sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / len(probs)


def brier_skill(
    model_probs: Sequence[float],
    baseline_probs: Sequence[float],
    outcomes: Sequence[int],
) -> float:
    """Fractional improvement of the model's Brier score over a baseline.

        skill = 1 - brier(model) / brier(baseline)

    Positive means the model beats the baseline. When the baseline is the
    market's own de-vigged price, ``skill <= 0`` means the market is at least
    as good as the model — which is the honest result for a liquid line, and
    the result this desk kept getting.
    """
    _check_pairs(model_probs, outcomes)
    _check_pairs(baseline_probs, outcomes)
    b_base = brier(baseline_probs, outcomes)
    if b_base == 0:
        raise ValueError("baseline Brier is 0 — skill is undefined against a perfect baseline")
    return 1.0 - brier(model_probs, outcomes) / b_base


def log_loss(probs: Sequence[float], outcomes: Sequence[int], eps: float = 1e-15) -> float:
    """Negative log-likelihood per observation. Punishes confident errors hard."""
    _check_pairs(probs, outcomes)
    total = 0.0
    for p, y in zip(probs, outcomes):
        p = min(max(p, eps), 1.0 - eps)
        total -= math.log(p) if y else math.log(1.0 - p)
    return total / len(probs)


# --------------------------------------------------------------------------
# Calibration
# --------------------------------------------------------------------------


def reliability_table(
    probs: Sequence[float], outcomes: Sequence[int], bins: int = 10
) -> list[dict]:
    """Bucket forecasts by predicted probability and report what actually happened.

    Returns one row per non-empty bin with ``n``, ``mean_pred`` and
    ``mean_actual``. A well-calibrated model has ``mean_pred ~= mean_actual``
    in every bin; the shape of the gap tells you *how* it is wrong
    (over-confident on favourites, under-priced tails, and so on).
    """
    _check_pairs(probs, outcomes)
    if bins < 1:
        raise ValueError("bins must be >= 1")
    buckets: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for p, y in zip(probs, outcomes):
        idx = min(int(p * bins), bins - 1)  # p == 1.0 belongs in the top bin
        buckets[idx].append((p, y))

    table = []
    for idx in sorted(buckets):
        rows = buckets[idx]
        table.append(
            {
                "bin_lo": idx / bins,
                "bin_hi": (idx + 1) / bins,
                "n": len(rows),
                "mean_pred": sum(p for p, _ in rows) / len(rows),
                "mean_actual": sum(y for _, y in rows) / len(rows),
            }
        )
    return table


def ece(probs: Sequence[float], outcomes: Sequence[int], bins: int = 10) -> float:
    """Expected calibration error — the sample-weighted mean gap in the
    reliability table.

    0.05 means that, on average, a stated probability is 5 percentage points
    away from the realised frequency. The promotion gate caps this because an
    uncalibrated model can look profitable on a lucky sample while being
    structurally mispriced.
    """
    table = reliability_table(probs, outcomes, bins=bins)
    n_total = sum(row["n"] for row in table)
    return sum(
        row["n"] / n_total * abs(row["mean_pred"] - row["mean_actual"]) for row in table
    )


# --------------------------------------------------------------------------
# Execution edge
# --------------------------------------------------------------------------


def clv_bps(entry_price: float, closing_price: float, side: str = "YES") -> float:
    """Closing-line value, in basis points of contract notional.

    A binary contract settles at 0 or 1, so the closing mid *is* the market's
    final probability. If we bought YES at 0.40 and it closed at 0.45, the
    market moved 5 points our way: +500 bps. Positive CLV over many decisions
    is the least self-flattering evidence that a signal contains information —
    it is measured against the market's own later opinion, not against our
    model, and it cannot be manufactured by a lucky settlement.

    ``side`` is ``"YES"`` or ``"NO"``; a NO position gains when the price falls.
    """
    side = side.upper()
    if side not in ("YES", "NO"):
        raise ValueError("side must be 'YES' or 'NO'")
    for name, val in (("entry_price", entry_price), ("closing_price", closing_price)):
        if not math.isfinite(val) or not 0.0 <= val <= 1.0:
            raise ValueError(f"{name} must be a probability in [0, 1], got {val!r}")
    move = closing_price - entry_price
    if side == "NO":
        move = -move
    return move * 10_000.0


# --------------------------------------------------------------------------
# Significance, respecting correlation
# --------------------------------------------------------------------------


def clustered_bootstrap_ci(
    values: Sequence[float],
    clusters: Sequence,
    confidence: float = 0.95,
    n_boot: int = 10_000,
    seed: int = 0,
) -> dict:
    """Bootstrap a mean by resampling *clusters*, not individual observations.

    This is the correction that matters most in practice and is skipped most
    often. Twenty strikeout props on the same game day are not twenty
    independent bets: they share a starting pitcher, a park, an umpire, a
    weather front. Resampling them individually pretends the sample is twenty
    times more informative than it is, and manufactures significance out of
    nothing.

    So: group observations by ``clusters`` (game day, event, session), then
    resample whole clusters with replacement. The interval widens — usually a
    lot — and marginal edges stop being significant. That is the correct
    answer, not a pessimistic one.

    Returns ``mean``, ``lo``, ``hi``, ``n``, ``n_clusters`` and ``significant``
    (whether the interval excludes zero).
    """
    if len(values) != len(clusters):
        raise ValueError("values and clusters must be the same length")
    if not values:
        raise ValueError("no observations")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")

    grouped: dict = defaultdict(list)
    for v, c in zip(values, clusters):
        grouped[c].append(float(v))
    keys = list(grouped)

    rng = random.Random(seed)
    means = []
    for _ in range(n_boot):
        pool: list[float] = []
        for _ in range(len(keys)):
            pool.extend(grouped[keys[rng.randrange(len(keys))]])
        means.append(sum(pool) / len(pool))
    means.sort()

    tail = (1.0 - confidence) / 2.0
    lo = means[int(tail * n_boot)]
    hi = means[min(int((1.0 - tail) * n_boot), n_boot - 1)]
    observed = sum(float(v) for v in values) / len(values)
    return {
        "mean": observed,
        "lo": lo,
        "hi": hi,
        "confidence": confidence,
        "n": len(values),
        "n_clusters": len(keys),
        "significant": lo > 0.0 or hi < 0.0,
    }


# --------------------------------------------------------------------------


def _check_pairs(probs: Sequence[float], outcomes: Sequence[int]) -> None:
    if len(probs) != len(outcomes):
        raise ValueError("probs and outcomes must be the same length")
    if not probs:
        raise ValueError("no observations")
    for p in probs:
        if not math.isfinite(p) or not 0.0 <= p <= 1.0:
            raise ValueError(f"probability out of range: {p!r}")
    for y in outcomes:
        if y not in (0, 1, True, False):
            raise ValueError(f"outcome must be 0 or 1, got {y!r}")


def mean(values: Iterable[float]) -> float:
    vals = list(values)
    if not vals:
        raise ValueError("no observations")
    return sum(vals) / len(vals)
