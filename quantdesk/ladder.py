"""The strategy lifecycle — and the gate that decides what gets capital.

Every idea the desk has enters here and climbs one rung at a time. Nothing
skips a rung, and nothing advances on the agent's enthusiasm::

    BACKLOG ──▶ RESEARCH ──▶ TICK ──▶ PAPER ──▶ READY ──▶ LIVE
                   │           │        │         │
                   └───────────┴────────┴─────────┴──────▶ RETIRED

    BACKLOG   an idea, not yet worked
    RESEARCH  offline validation; must beat a real baseline out-of-sample
    TICK      live data collection; proving the feed is fresh and clean
    PAPER     recorded decisions against live prices, settled on real outcomes
    READY     the paper evidence cleared every bar; awaiting capital
    LIVE      real money at risk
    RETIRED   killed

The interesting rung is **PAPER → READY**, and it is deliberately hard:

* at least 20 settled decisions, over at least 15 **independent** days —
  because twenty props on one game day are not twenty samples;
* fee-net closing-line value positive **and** significant under a
  day-clustered bootstrap;
* realised paper P&L above zero after fees;
* calibration error still inside the ceiling on live data;
* better than the market-implied baseline;
* and ``provenance == "ledger"`` — the metrics must have been *computed* from
  the settled ledger by :mod:`quantdesk.metrics`, not typed in. A strategy
  whose numbers were asserted rather than derived cannot clear this gate no
  matter how good the numbers look.

READY and LIVE additionally require a fresh PROCEED artifact from
:mod:`quantdesk.panel`, and LIVE requires :mod:`quantdesk.sandbox` to approve
the worst-case loss. With the cap where it was, strategies parked at READY.
None ever reached LIVE. The ledger of what did happen is in
``evidence/registry.json``: 34 candidates, 14 retired, one that got as far as
PAPER, and zero that cleared the gate.

CLI::

    python -m quantdesk.ladder list
    python -m quantdesk.ladder list --stage RETIRED
    python -m quantdesk.ladder show mlb_kprop
    python -m quantdesk.ladder adjudicate --all
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

from . import panel, sandbox
from .paths import POLICY_FILE, REGISTRY_FILE

__all__ = ["Ruling", "load_policy", "load_registry", "adjudicate", "promote", "kill_reason"]


@dataclass(frozen=True)
class Ruling:
    """What the gate thinks should happen next, and exactly why."""

    action: str  # RESEARCH | TICK | PAPER | READY | LIVE | HOLD | RETIRE
    reason: str
    failures: tuple[str, ...] = ()

    def __str__(self) -> str:
        return f"{self.action}: {self.reason}"


def load_policy(path=None) -> dict:
    with open(path or POLICY_FILE) as fh:
        return json.load(fh)


def load_registry(path=None) -> list[dict]:
    with open(path or REGISTRY_FILE) as fh:
        return json.load(fh)["strategies"]


# --------------------------------------------------------------------------
# Kill criteria — checked first, at every stage
# --------------------------------------------------------------------------


def kill_reason(metrics: dict, policy: dict) -> str | None:
    """Any one of these true and the candidate is retired.

    Killing early is cheap and reversible. Capital is not.
    """
    if metrics.get("oos_loses_to_baseline"):
        return "loses to the baseline out-of-sample"
    if metrics.get("edge_gone_at_touch"):
        return "edge disappears at the executable touch (it was a mid-price mirage)"
    if metrics.get("data_leaky_or_stale"):
        return "input data is leaky or stale"
    if metrics.get("decalibrated"):
        return "calibration broke down on live data"
    floor = policy["kill"]["min_settlements_for_pnl_kill"]
    if (
        metrics.get("n_settlements", 0) >= floor
        and (metrics.get("paper_pnl") or 0) < 0
        and metrics.get("paper_pnl_significant")
    ):
        return f"paper P&L significantly negative over {metrics['n_settlements']} settlements"
    return None


# --------------------------------------------------------------------------
# Adjudication — a pure function of the recorded evidence
# --------------------------------------------------------------------------


def adjudicate(strategy: dict, policy: dict | None = None) -> Ruling:
    """Recommend the next rung. Pure: same evidence in, same ruling out.

    Deliberately separate from :func:`promote`, so the agent can ask "what
    would happen?" as often as it likes without anything moving.
    """
    policy = policy or load_policy()
    metrics = strategy.get("metrics") or {}
    stage = (strategy.get("stage") or "").upper()

    if stage != "RETIRED":
        why = kill_reason(metrics, policy)
        if why:
            return Ruling("RETIRE", why)

    if stage == "BACKLOG":
        return Ruling("RESEARCH", "pull into research")

    if stage == "RESEARCH":
        bars = policy["research"]
        if not metrics.get("oos_beats_baseline"):
            return Ruling("HOLD", "does not yet beat the out-of-sample baseline",
                          ("oos_beats_baseline",))
        ece = metrics.get("ece")
        if ece is not None and ece > bars["max_ece"]:
            return Ruling(
                "HOLD",
                f"calibration ECE {ece:.3f} > {bars['max_ece']:.3f}",
                ("max_ece",),
            )
        return Ruling("PAPER", "beats the OOS baseline and is calibrated — wire it to live paper")

    if stage == "TICK":
        return Ruling("PAPER", "tick logging complete — begin recorded paper fills")

    if stage == "PAPER":
        return _adjudicate_paper(metrics, policy["paper"])

    if stage == "READY":
        return Ruling("LIVE", "requires a panel PROCEED and spend-gate approval")

    return Ruling("HOLD", f"stage {stage or 'UNKNOWN'}: no automatic transition")


def _adjudicate_paper(metrics: dict, bars: dict) -> Ruling:
    clv = metrics.get("clv_bps")
    pnl = metrics.get("paper_pnl")
    ece = metrics.get("ece")

    checks = [
        (
            metrics.get("n_settlements", 0) >= bars["min_settlements"],
            f"settlements {metrics.get('n_settlements', 0)}/{bars['min_settlements']}",
        ),
        (
            metrics.get("n_independent_days", metrics.get("n_station_days", 0))
            >= bars["min_independent_days"],
            f"independent days "
            f"{metrics.get('n_independent_days', metrics.get('n_station_days', 0))}"
            f"/{bars['min_independent_days']}",
        ),
        (
            clv is not None and clv >= bars["min_clv_bps"] and bool(metrics.get("clv_significant")),
            "closing-line value not measured"
            if clv is None
            else f"fee-net CLV {_fmt(clv)} bps, significant={metrics.get('clv_significant')}",
        ),
        (pnl is not None and pnl > bars["min_paper_pnl"], f"paper P&L {_fmt(pnl)}"),
        (ece is None or ece <= bars["max_ece"], f"calibration ECE {_fmt(ece)}"),
        (
            bool(metrics.get("beats_market_baseline")),
            f"beats market baseline: {metrics.get('beats_market_baseline')}",
        ),
        (
            metrics.get("provenance") == bars["provenance"],
            f"metrics provenance '{metrics.get('provenance')}' "
            f"(need '{bars['provenance']}' — computed from the ledger, not asserted)",
        ),
    ]

    failures = tuple(why for ok, why in checks if not ok)
    if failures:
        return Ruling("HOLD", "paper gate not cleared — " + "; ".join(failures), failures)
    return Ruling("READY", "cleared every paper bar — capital-ready, pending a panel PROCEED")


# --------------------------------------------------------------------------
# Promotion — the side-effecting half, and where the other gates are enforced
# --------------------------------------------------------------------------


def promote(
    strategy: dict,
    to: str,
    *,
    policy: dict | None = None,
    worst_case_usd: float | None = None,
    now=None,
    verdict_dirs=None,
    commit_spend: bool = True,
) -> Ruling:
    """Attempt to move ``strategy`` to stage ``to``. Fails closed.

    Returns a :class:`Ruling` whose action is the new stage on success, or
    ``BLOCKED`` with the reason. The strategy dict is mutated only on success.
    """
    policy = policy or load_policy()
    ladder = policy["ladder"]
    to = to.upper()
    stage = (strategy.get("stage") or "").upper()

    if to not in ladder and to != "RETIRED":
        return Ruling("BLOCKED", f"{to} is not a stage")
    if to != "RETIRED":
        if stage not in ladder:
            return Ruling("BLOCKED", f"cannot promote out of {stage or 'UNKNOWN'}")
        if ladder.index(to) != ladder.index(stage) + 1:
            return Ruling(
                "BLOCKED",
                f"{stage} -> {to} skips a rung; candidates advance one at a time",
            )

    # Evidence gate: would adjudication have recommended this move on its own?
    ruling = adjudicate(strategy, policy)
    if to != "RETIRED" and ruling.action != to:
        return Ruling("BLOCKED", f"evidence does not support {to} — {ruling.reason}",
                      ruling.failures)

    # Review gate.
    if to in policy["panel"]["required_for_stages"]:
        verdict = panel.find_proceed(
            strategy["id"],
            max_age_h=policy["panel"]["max_verdict_age_hours"],
            now=now,
            dirs=verdict_dirs,
        )
        if verdict is None:
            return Ruling(
                "BLOCKED",
                f"no PROCEED artifact for '{strategy['id']}' inside the "
                f"{policy['panel']['max_verdict_age_hours']:g}h window — "
                "run quantdesk.panel first (a claim that the panel passed is not evidence)",
            )

    # Money gate.
    if to == "LIVE" and policy["live"]["require_spend_approval"]:
        if worst_case_usd is None or not worst_case_usd > 0:
            return Ruling("BLOCKED", "LIVE requires an explicit worst-case loss above $0")
        decision = sandbox.request(
            worst_case_usd,
            f"go live: {strategy['id']}",
            commit=commit_spend,
        )
        if not decision.approved:
            return Ruling("BLOCKED", f"spend gate refused — {decision.reason}")

    strategy["stage"] = to
    strategy.setdefault("history", []).append(
        {
            "ts": (now or datetime.now(timezone.utc)).isoformat(),
            "event": f"{stage} -> {to}: {ruling.reason}",
        }
    )
    return Ruling(to, ruling.reason)


def _fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


# --------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Strategy lifecycle registry and promotion gate")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="list candidates")
    p_list.add_argument("--stage", default=None)

    p_show = sub.add_parser("show", help="show one candidate in full")
    p_show.add_argument("id")

    p_adj = sub.add_parser("adjudicate", help="what would the gate do?")
    p_adj.add_argument("id", nargs="?")
    p_adj.add_argument("--all", action="store_true")

    args = ap.parse_args(argv[1:])
    policy = load_policy()
    strategies = load_registry()

    if args.cmd == "list":
        rows = strategies
        if args.stage:
            rows = [s for s in rows if s["stage"] == args.stage.upper()]
        print(f"{'ID':34s} {'STAGE':9s} {'N':>5s} {'CLV bps':>9s} {'P&L':>9s} {'ECE':>7s}")
        print("-" * 78)
        for s in rows:
            m = s.get("metrics") or {}
            print(
                f"{s['id'][:34]:34s} {s['stage']:9s} "
                f"{_fmt(m.get('n_settlements')):>5s} {_fmt(m.get('clv_bps')):>9s} "
                f"{_fmt(m.get('paper_pnl')):>9s} {_fmt(m.get('ece')):>7s}"
            )
        print(f"\n{len(rows)} candidates")
        return 0

    if args.cmd == "show":
        for s in strategies:
            if s["id"] == args.id:
                print(json.dumps(s, indent=2))
                return 0
        print(f"no such strategy: {args.id}")
        return 1

    if args.cmd == "adjudicate":
        rows = strategies if args.all else [s for s in strategies if s["id"] == args.id]
        if not rows:
            print("nothing to adjudicate (pass an id or --all)")
            return 1
        for s in rows:
            print(f"{s['id'][:34]:34s} {s['stage']:9s} -> {adjudicate(s, policy)}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
