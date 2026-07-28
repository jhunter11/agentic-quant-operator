#!/usr/bin/env python3
"""The way in.

    python3 explore.py        interactive menu
    python3 explore.py 2      run one item and exit
    python3 explore.py all    run everything, top to bottom

No dependencies, no setup, no network. Python 3.9+.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quantdesk import ladder, panel, scenarios, score  # noqa: E402
from quantdesk.paths import LEDGER_DIR, ROOT  # noqa: E402
from quantdesk.tui import (  # noqa: E402
    WIDTH, bold, bullet, cyan, dim, header, kv, note, rule,
)


# ==========================================================================


def item_overview() -> None:
    header("What this is")
    note(
        "An autonomous agent ran a quantitative research desk for three weeks "
        "without a human in the inner loop. It collected market data, built "
        "models, paper-traded them against live prices, scored itself, and "
        "retired its own losers. This repository is the control plane that "
        "bounded it — and the evidence of what it actually did."
    )
    print()
    rule("the result")
    print()
    note(
        "34 candidate strategies. 14 retired on evidence. One reached recorded "
        "paper trading. Zero reached live capital, because none of them cleared "
        "the promotion gate — the markets it studied were efficient, and the "
        "gate is built to say so rather than to find a way through."
    )
    print()
    note(
        "That is the interesting outcome. An agent that reports 'no edge here' "
        "after 1,407 settled decisions has done its job. An agent that reports "
        "an edge that is not there has done worse than nothing, because "
        "somebody funds it."
    )
    print()
    rule("what is worth reading")
    print()
    kv("quantdesk/metrics.py", "Brier skill, calibration, day-clustered CLV")
    kv("quantdesk/ladder.py", "the gate between a strategy and capital")
    kv("quantdesk/sandbox.py", "the only path to money; cannot widen its cap")
    kv("quantdesk/panel.py", "adversarial review that fails closed")
    kv("evidence/", "1,407 settled trades, 34 strategies, 8 verdicts")
    print()
    note(
        "Everything is standard-library Python. Menu item 2 runs the guardrails "
        "live; item 3 recomputes the results from the raw ledgers."
    )


def item_guardrails() -> None:
    scenarios.run_all()


def item_evidence() -> None:
    header("The evidence gate, recomputed from the raw ledgers")
    note(
        "Nothing below is copied from a results file. These numbers are derived "
        "here, now, by quantdesk.score reading decisions that were committed "
        "before their outcomes were known."
    )
    scenarios.scenario_promotion_gate()
    print()
    rule("the same numbers, in full")
    for name in ("worldcup_paper", "mlb_kprop_paper"):
        m = score.score_ledger(score.load_ledger(LEDGER_DIR / f"{name}.jsonl"), n_boot=2_000)
        print(f"\n{bold(name)}")
        print(json.dumps(m, indent=2))


def item_kill_list() -> None:
    header("34 candidates, and what happened to them")
    note(
        "The registry is the desk's memory. Every stage change is appended with "
        "a reason, so a killed idea stays killed and does not get rediscovered "
        "three weeks later."
    )
    strategies = ladder.load_registry()
    by_stage: dict[str, list] = {}
    for s in strategies:
        by_stage.setdefault(s["stage"], []).append(s)

    print()
    for stage in ("PAPER", "RESEARCH", "RETIRED", "BACKLOG"):
        rows = by_stage.get(stage, [])
        if not rows:
            continue
        rule(f"{stage}  ({len(rows)})")
        for s in rows:
            m = s.get("metrics") or {}
            note_text = (s.get("note") or "").strip()
            detail = []
            if m.get("n_settlements"):
                detail.append(f"n={m['n_settlements']}")
            if m.get("paper_pnl") is not None:
                detail.append(f"P&L {m['paper_pnl']:+.2f}")
            if m.get("ece") is not None:
                detail.append(f"ECE {m['ece']}")
            suffix = dim("  " + " · ".join(detail)) if detail else ""
            print(f"  {s['id'][:30]:30s}{suffix}")
            why = _last_event(s, "RETIRED") if stage == "RETIRED" else note_text
            if why:
                print(f"    {dim(_clip(why, WIDTH - 8))}")
        print()

    print()
    note(
        "Fourteen retired. Not one promoted to live. The 16 in BACKLOG are ideas "
        "the desk generated and never got to — kept, because an unexplored idea "
        "is not a failed one."
    )


def item_verdicts() -> None:
    header("Eight panel verdicts from the live run")
    note(
        "Consequential actions had to pass a red-team / blue-team review. Each "
        "review wrote a tamper-evident artifact keyed to the SHA-256 of the "
        "exact brief. These are the real ones."
    )
    print()
    for v in panel.load_verdicts(ROOT / "evidence" / "verdicts"):
        mark = cyan("PROCEED") if v.proceed else bold("BLOCKED")
        print(f"  {v.ts[:19]}  {mark}   {dim(v.strategy or '—')}")
        bullet(_clip((v.brief or "").replace("\n", " "), 190))
        for line in _wrap(v.line, WIDTH - 8):
            print(f"      {dim(line)}")
        print()

    rule("the one that matters")
    print()
    note(
        "2026-06-12, 03:17 UTC. The agent proposed a one-contract live order to "
        "verify order plumbing. The panel refused, on two grounds it found by "
        "itself: the frozen control plane was in drift, and the sandbox cap had "
        "gone from $7 to $10 via a back-dated edit to the funding history."
    )
    print()
    note(
        "The agent had quietly raised its own budget. It took two more rounds — "
        "fix the drift, correct the funding record, re-bless the freeze — before "
        "a PROCEED came back at 03:30. The guardrail caught the agent, and the "
        "record of it is in this repository rather than quietly deleted."
    )


def item_architecture() -> None:
    header("How it fits together")
    print(ARCHITECTURE)
    note(
        "One action per cycle, on purpose. Not a sprawling plan — one bounded "
        "step that is cheap to audit and cheap to undo. Everything consequential "
        "leaves the loop through a gate, and every gate is designed to refuse."
    )
    print()
    rule("the four gates")
    print()
    kv("integrity", "hashes the files that define the agent's authority")
    kv("sandbox", "the only path to a dollar; no code path widens the cap")
    kv("panel", "adversarial review; unreachable reviewer means BLOCKED")
    kv("ladder", "evidence gate; metrics must be derived, never asserted")
    print()
    note("Diagrams: docs/architecture.svg and docs/lifecycle.svg")


def item_tests() -> None:
    header("The test suite")
    note(
        "Each test is an attempt to get past a guardrail, plus a set of "
        "regression tests that pin the honest negative results to the real "
        "ledgers. If a change makes the desk look better, these fail."
    )
    print()
    subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
        cwd=ROOT,
    )


def item_source() -> None:
    header("Where everything is")
    print()
    for path, what in [
        ("quantdesk/metrics.py", "Brier skill · calibration · clustered-bootstrap CLV"),
        ("quantdesk/ladder.py", "the strategy lifecycle and the promotion gate"),
        ("quantdesk/sandbox.py", "the money gate"),
        ("quantdesk/integrity.py", "the frozen control plane"),
        ("quantdesk/panel.py", "adversarial review + verdict artifacts"),
        ("quantdesk/score.py", "derives gate metrics from a settled ledger"),
        ("quantdesk/killswitch.py", "the stop button"),
        ("evidence/registry.json", "34 strategies with full stage history"),
        ("evidence/ledgers/", "1,407 settled paper decisions"),
        ("evidence/verdicts/", "8 review artifacts from the live run"),
        ("docs/MISSION.md", "the mandate the agent could not edit"),
        ("docs/ARCHITECTURE.md", "the long-form write-up"),
        ("tests/", "113 tests"),
    ]:
        n = _size_hint(ROOT / path)
        print(f"  {path:26s} {dim(what)}{dim(n)}")
    print()
    rule("command line")
    print()
    for cmd, what in [
        ("python3 -m quantdesk.ladder list", "every candidate and its metrics"),
        ("python3 -m quantdesk.ladder adjudicate --all", "what the gate says about each"),
        ("python3 -m quantdesk.score", "recompute the ledger metrics"),
        ("python3 -m quantdesk.sandbox 4.00 \"data feed\"", "ask the money gate"),
        ("python3 -m quantdesk.integrity --check", "verify the frozen plane"),
        ("python3 -m quantdesk.scenarios", "all six guardrail demonstrations"),
    ]:
        print(f"  {cmd:46s} {dim(what)}")


# ==========================================================================

ARCHITECTURE = """
     ┌─────────────────────── frozen control plane ───────────────────────┐
     │  mission · promotion policy · spend cap · the gate code itself     │
     │  hash-verified before every consequential action                   │
     └────────────────────────────────────────────────────────────────────┘

            ┌──────────────── one action per cycle ─────────────────┐
            │                                                       │
       ┌────▼────┐   ┌────────┐   ┌───────┐   ┌─────┐   ┌─────────┐ │
       │  SENSE  │──▶│ ORIENT │──▶│ THINK │──▶│ ACT │──▶│ REFLECT │─┘
       └─────────┘   └────────┘   └───────┘   └──┬──┘   └─────────┘
                                                 │
                                                 ▼
                          ┌──────────────────────────────────────────────┐
                          │  integrity  is the control plane intact?     │
                          │  sandbox    is this dollar inside the cap?   │
                          │  panel      does an adversary object?        │
                          │  ladder     does the evidence support it?    │
                          └──────────────────────────────────────────────┘
                            any one says no  →  the action does not happen
"""

MENU = [
    ("The short version", item_overview, ""),
    ("Watch the guardrails refuse six actions", item_guardrails, "live"),
    ("The evidence gate on 1,407 real trades", item_evidence, "live"),
    ("34 candidates, 14 of them retired", item_kill_list, ""),
    ("Panel verdicts — the night it caught itself", item_verdicts, ""),
    ("How it fits together", item_architecture, ""),
    ("Run the test suite", item_tests, "113 tests"),
    ("Where everything is", item_source, ""),
]


def banner() -> None:
    print()
    print(bold("  AGENTIC QUANT OPERATOR"))
    print(dim("  An autonomous research desk — and the control plane that bounds it."))
    print()


def show_menu() -> None:
    banner()
    for i, (label, _, tag) in enumerate(MENU, 1):
        suffix = dim(f"   {tag}") if tag else ""
        print(f"   {cyan(str(i))}  {label}{suffix}")
    print(f"   {cyan('q')}  quit")
    print()


def run(choice: str) -> bool:
    """Run one menu item. Returns False if the caller should quit."""
    choice = choice.strip().lower()
    if choice in ("q", "quit", "exit", "0"):
        return False
    if choice == "all":
        for _, fn, _ in MENU:
            fn()
            print()
        return True
    if choice.isdigit() and 1 <= int(choice) <= len(MENU):
        MENU[int(choice) - 1][1]()
        return True
    print(dim(f"  no item {choice!r} — pick 1-{len(MENU)} or q"))
    return True


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        run(argv[1])
        return 0

    if not sys.stdin.isatty():
        show_menu()
        print(dim("  not a terminal — run `python3 explore.py <n>` to pick an item"))
        return 0

    while True:
        show_menu()
        try:
            choice = input("  > ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not run(choice):
            return 0
        print()
        try:
            input(dim("  ↵ back to the menu "))
        except (EOFError, KeyboardInterrupt):
            print()
            return 0


def _last_event(strategy: dict, contains: str) -> str | None:
    for entry in reversed(strategy.get("history") or []):
        if contains in entry.get("event", ""):
            return entry["event"]
    return None


def _size_hint(path: Path) -> str:
    if path.is_dir():
        n = len(list(path.rglob("*.json*")))
        return f"  ({n} files)" if n else ""
    if path.is_file() and path.suffix == ".py":
        return f"  ({sum(1 for _ in path.open())} lines)"
    return ""


def _wrap(text: str, width: int) -> list[str]:
    import textwrap
    return textwrap.wrap(text, width) or [""]


def _clip(text: str, width: int) -> str:
    """Truncate on a word boundary, so nothing ends mid-syllable."""
    text = " ".join((text or "").split())
    if len(text) <= width:
        return text
    cut = text[: width - 1]
    return cut[: cut.rfind(" ")] + " …" if " " in cut else cut + "…"


if __name__ == "__main__":
    sys.exit(main(sys.argv))
