"""The stop button.

A file-based flag, on purpose. When ``runtime/TRADING_PAUSED`` exists,
:mod:`quantdesk.sandbox` refuses every spend and any live order path refuses to
run. No daemon to be alive, no socket to be reachable, no state in a process
that might be the thing that is wedged — an operator with a shell and nothing
else can stop the desk, and a partially-broken agent cannot restart it by
accident.

The repair protocol the loop is required to follow::

    1  killswitch pause "<reason>"
    2  apply the fix
    3  restart the affected services
    4  verify — integrity check plus a targeted test
    5  killswitch resume

CLI::

    python -m quantdesk.killswitch pause "settlement join looks wrong"
    python -m quantdesk.killswitch status
    python -m quantdesk.killswitch resume
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from .paths import TRADING_PAUSED_FLAG, ensure_runtime

__all__ = ["pause", "resume", "is_paused", "state"]


def pause(reason: str, *, flag=None) -> dict:
    flag = flag or TRADING_PAUSED_FLAG
    ensure_runtime()
    payload = {"ts": datetime.now(timezone.utc).isoformat(), "reason": reason}
    with open(flag, "w") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    return payload


def resume(*, flag=None) -> bool:
    """Lift the pause. Returns whether a pause was actually in place."""
    flag = flag or TRADING_PAUSED_FLAG
    if not flag.exists():
        return False
    flag.unlink()
    return True


def is_paused(*, flag=None) -> bool:
    return (flag or TRADING_PAUSED_FLAG).exists()


def state(*, flag=None) -> dict:
    flag = flag or TRADING_PAUSED_FLAG
    if not flag.exists():
        return {"paused": False}
    try:
        with open(flag) as fh:
            payload = json.load(fh)
        return {"paused": True, **payload}
    except Exception:
        return {"paused": True, "ts": "?", "reason": "(flag unreadable)"}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Live-trading kill-switch")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pause")
    p.add_argument("reason")
    sub.add_parser("resume")
    sub.add_parser("status")
    args = ap.parse_args(argv[1:])

    if args.cmd == "pause":
        payload = pause(args.reason)
        print(f"PAUSED at {payload['ts']}")
        print(f"  reason : {payload['reason']}")
        print("  -> every spend and live order path will now be DENIED")
        return 0

    if args.cmd == "resume":
        print("RESUMED" if resume() else "not paused — nothing to do")
        return 0

    st = state()
    if st["paused"]:
        print("STATUS: PAUSED")
        print(f"  since  : {st.get('ts')}")
        print(f"  reason : {st.get('reason')}")
    else:
        print("STATUS: active")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
