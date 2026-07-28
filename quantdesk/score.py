"""Compute gate metrics *from* a settled ledger — never by hand.

This module is the reason ``provenance`` exists in the promotion policy. The
gate in :mod:`quantdesk.ladder` refuses any metrics block that was not produced
here, because the single easiest way for an autonomous agent to promote a bad
strategy is to write down good numbers for it. Making the gate read only
*derived* evidence closes that door: to clear the bar, the ledger itself has to
clear the bar.

A ledger row is one decision that was committed before the outcome was known::

    {"event": ..., "event_date": "2026-06-16", "side": "YES",
     "model_p": 0.7855,        # our probability, stamped at decision time
     "entry_price": 0.695,     # the market's probability, same moment
     "closing_price": 0.985,   # the market's final probability  (optional)
     "outcome": 1,             # what actually happened
     "pnl": 2.0}               # realised, fee-net

``entry_price`` doubles as the market baseline: on a binary contract the price
*is* the market's stated probability, so "did we beat the market?" is a Brier
skill score against it, with no modelling assumption of our own.

Anything the ledger cannot support comes back as ``None``, and ``None`` fails
the gate. That distinction matters more than it looks: the MLB k-prop family
below has 1,364 settled decisions and *no* CLV, because the closing-quote
capture never populated. Reporting that as "CLV = 0" would read as a flat
result; reporting it as ``None`` reads as "not measured", which is the truth
and is a gate failure.

CLI::

    python -m quantdesk.score                      # score every ledger
    python -m quantdesk.score worldcup_paper       # score one
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import metrics
from .paths import LEDGER_DIR

__all__ = ["load_ledger", "score_ledger", "score_all"]


def load_ledger(path) -> list[dict]:
    rows = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def score_ledger(rows: list[dict], *, n_boot: int = 5_000, seed: int = 0) -> dict:
    """Derive the full metrics block the promotion gate reads."""
    rows = [r for r in rows if r.get("outcome") in (0, 1) and r.get("model_p") is not None]
    if not rows:
        return {"provenance": "ledger", "n_settlements": 0}

    model_p = [float(r["model_p"]) for r in rows]
    outcomes = [int(r["outcome"]) for r in rows]
    days = [r.get("event_date") or (r.get("decision_ts") or "")[:10] for r in rows]

    out = {
        "provenance": "ledger",
        "n_settlements": len(rows),
        "n_independent_days": len(set(days)),
        "paper_pnl": round(sum(float(r.get("pnl") or 0.0) for r in rows), 4),
        "brier_model": round(metrics.brier(model_p, outcomes), 4),
        "ece": round(metrics.ece(model_p, outcomes), 4),
    }

    # --- market baseline -------------------------------------------------
    market_p = [
        r.get("market_p") if r.get("market_p") is not None else r.get("entry_price")
        for r in rows
    ]
    if all(p is not None for p in market_p):
        market_p = [float(p) for p in market_p]
        out["brier_market"] = round(metrics.brier(market_p, outcomes), 4)
        skill = metrics.brier_skill(model_p, market_p, outcomes)
        out["skill_vs_market"] = round(skill, 4)
        out["beats_market_baseline"] = skill > 0
    else:
        out["brier_market"] = None
        out["skill_vs_market"] = None
        out["beats_market_baseline"] = False

    # --- closing-line value ----------------------------------------------
    clv_rows = [
        r for r in rows
        if r.get("closing_price") is not None and r.get("entry_price") is not None
    ]
    if clv_rows:
        clv = [
            metrics.clv_bps(
                float(r["entry_price"]), float(r["closing_price"]), r.get("side", "YES")
            )
            for r in clv_rows
        ]
        clv_days = [r.get("event_date") or (r.get("decision_ts") or "")[:10] for r in clv_rows]
        ci = metrics.clustered_bootstrap_ci(clv, clv_days, n_boot=n_boot, seed=seed)
        out["clv_bps"] = round(ci["mean"], 2)
        out["clv_ci"] = [round(ci["lo"], 2), round(ci["hi"], 2)]
        out["clv_significant"] = ci["significant"]
        out["n_clv"] = ci["n"]
        out["n_clv_clusters"] = ci["n_clusters"]
    else:
        # Not measured. Not zero. The gate must be able to tell these apart.
        out["clv_bps"] = None
        out["clv_significant"] = False
        out["n_clv"] = 0

    # --- P&L significance, for the kill rule ------------------------------
    pnl = [float(r.get("pnl") or 0.0) for r in rows]
    if any(pnl):
        ci = metrics.clustered_bootstrap_ci(pnl, days, n_boot=n_boot, seed=seed)
        out["paper_pnl_significant"] = ci["significant"]
        out["paper_pnl_ci"] = [round(ci["lo"], 4), round(ci["hi"], 4)]

    return out


def score_all(ledger_dir=None, **kw) -> dict[str, dict]:
    ledger_dir = Path(ledger_dir or LEDGER_DIR)
    return {
        p.stem: score_ledger(load_ledger(p), **kw)
        for p in sorted(ledger_dir.glob("*.jsonl"))
    }


def main(argv: list[str]) -> int:
    which = argv[1] if len(argv) > 1 else None
    results = score_all()
    if which:
        results = {k: v for k, v in results.items() if k == which or k.startswith(which)}
        if not results:
            print(f"no ledger named {which!r} in {LEDGER_DIR}")
            return 1
    for name, m in results.items():
        print(f"\n=== {name} ===")
        print(json.dumps(m, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
