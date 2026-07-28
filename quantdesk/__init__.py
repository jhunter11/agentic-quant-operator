"""quantdesk — the control plane of an autonomous quantitative research desk.

Six small modules, no third-party dependencies. Each one is a gate that the
agent has to get through, and each one is designed to say no:

    sandbox     the only path to money; cannot widen its own cap
    integrity   hashes the files that define the agent's authority
    panel       adversarial review; fails closed; writes tamper-evident verdicts
    ladder      the strategy lifecycle and the evidence gate before capital
    metrics     forward evaluation — Brier skill, calibration, clustered CLV
    score       derives gate metrics from a settled ledger, so they can't be typed
    killswitch  a file-based stop button that works when everything else is wedged
"""

__version__ = "1.0.0"

__all__ = [
    "integrity",
    "killswitch",
    "ladder",
    "metrics",
    "panel",
    "sandbox",
    "score",
]
