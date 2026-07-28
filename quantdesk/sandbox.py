"""The money gate — the only path from the agent to a dollar.

Every action that costs money must call :func:`request`. There is no second
path, and there is deliberately **no code in this module that raises the cap**.
The agent can spend down to the limit and not one cent past it; changing the
limit is an operator edit to ``config/sandbox.json``, which lives in git and
therefore leaves a diff.

That asymmetry is the whole design. The agent is trusted to *choose* spending;
it is not trusted to *authorise* it.

Fail-closed cases, all of which were reachable in practice:

    trading paused        the kill-switch flag is present -> DENIED
    NaN / inf amount      ``nan > x`` is False, so a naive check approves it -> DENIED
    zero or negative      a "$0 spend" must never mint an APPROVED receipt -> DENIED
    corrupt state file    negative or non-finite limit/spent -> DENIED, operator repairs

CLI::

    python -m quantdesk.sandbox 4.00 "the-odds-api overage"
    python -m quantdesk.sandbox --status
"""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

from .paths import SANDBOX_FILE, TRADING_PAUSED_FLAG

__all__ = ["Decision", "request", "status", "SpendDenied"]


class SpendDenied(Exception):
    """Raised by :func:`require` when the gate refuses."""


@dataclass(frozen=True)
class Decision:
    approved: bool
    reason: str
    amount_usd: float = 0.0
    remaining_usd: float = 0.0
    limit_usd: float = 0.0

    def __str__(self) -> str:  # what the CLI prints
        tag = "APPROVED" if self.approved else "DENIED"
        return f"{tag}: {self.reason}"


def _load(path=None) -> dict:
    with open(path or SANDBOX_FILE) as fh:
        return json.load(fh)


def _save(state: dict, path=None) -> None:
    path = str(path or SANDBOX_FILE)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)  # atomic: a crash mid-write cannot corrupt the ledger


def request(
    amount_usd: float,
    reason: str,
    *,
    sandbox_file=None,
    paused_flag=None,
    commit: bool = True,
) -> Decision:
    """Ask to commit ``amount_usd``. Returns a :class:`Decision`; records the
    spend against the sandbox ledger when approved and ``commit`` is true.

    The recorded total is durable, so the cap holds across process restarts —
    an agent cannot reset its own budget by crashing.
    """
    sandbox_file = sandbox_file or SANDBOX_FILE
    paused_flag = paused_flag or TRADING_PAUSED_FLAG

    if os.path.exists(paused_flag):
        return Decision(False, f"trading paused — {_pause_reason(paused_flag)}")

    try:
        amount = round(float(amount_usd), 2)
    except (TypeError, ValueError):
        return Decision(False, "amount is not a number")

    # NaN and inf silently pass every naive comparison; reject them explicitly.
    if not math.isfinite(amount):
        return Decision(False, "amount is not a finite number")
    if amount <= 0:
        return Decision(False, "amount must be a positive dollar value")
    if not (reason or "").strip():
        return Decision(False, "every spend must carry a reason (it goes in the ledger)")

    state = _load(sandbox_file)
    limit = float(state.get("limit_usd", 0.0))
    spent = float(state.get("spent_usd", 0.0))
    if not (math.isfinite(limit) and math.isfinite(spent)) or limit < 0 or spent < 0:
        return Decision(
            False,
            "sandbox state is corrupt (non-finite or negative limit/spent) — "
            "operator must repair config/sandbox.json before any spend",
        )

    remaining = round(limit - spent, 2)
    if amount > remaining:
        return Decision(
            False,
            f"${amount:.2f} exceeds the ${remaining:.2f} remaining of a "
            f"${limit:.2f} cap — raising the cap is an operator action",
            amount_usd=amount,
            remaining_usd=remaining,
            limit_usd=limit,
        )

    new_remaining = round(limit - round(spent + amount, 2), 2)
    if commit:
        state["spent_usd"] = round(spent + amount, 2)
        state.setdefault("ledger", []).append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "amount_usd": amount,
                "reason": reason,
                "remaining_after_usd": new_remaining,
            }
        )
        _save(state, sandbox_file)

    return Decision(
        True,
        f'${amount:.2f} for "{reason}" — ${new_remaining:.2f} of ${limit:.2f} left',
        amount_usd=amount,
        remaining_usd=new_remaining,
        limit_usd=limit,
    )


def require(amount_usd: float, reason: str, **kw) -> Decision:
    """:func:`request`, but raises :class:`SpendDenied` instead of returning a
    refusal — for call sites that must not be able to ignore the answer."""
    decision = request(amount_usd, reason, **kw)
    if not decision.approved:
        raise SpendDenied(decision.reason)
    return decision


def status(*, sandbox_file=None, paused_flag=None) -> dict:
    """Current cap, spend, and remaining headroom."""
    sandbox_file = sandbox_file or SANDBOX_FILE
    state = _load(sandbox_file)
    limit = float(state.get("limit_usd", 0.0))
    spent = float(state.get("spent_usd", 0.0))
    return {
        "limit_usd": limit,
        "spent_usd": spent,
        "remaining_usd": round(limit - spent, 2),
        "n_spends": len(state.get("ledger", [])),
        "paused": os.path.exists(paused_flag or TRADING_PAUSED_FLAG),
    }


def _pause_reason(flag) -> str:
    try:
        with open(flag) as fh:
            payload = json.load(fh)
        return f"paused at {payload.get('ts', '?')}: {payload.get('reason', '?')}"
    except Exception:
        return "paused (reason unreadable)"


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] in ("--status", "status"):
        st = status()
        state = "PAUSED" if st["paused"] else "active"
        print(
            f"sandbox: ${st['spent_usd']:.2f} spent of ${st['limit_usd']:.2f} cap "
            f"(${st['remaining_usd']:.2f} left, {st['n_spends']} spends, {state})"
        )
        return 0
    if len(argv) < 3:
        print('usage: python -m quantdesk.sandbox <amount_usd> "<reason>"')
        print("       python -m quantdesk.sandbox --status")
        return 2
    decision = request(argv[1], argv[2])
    print(decision)
    return 0 if decision.approved else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
