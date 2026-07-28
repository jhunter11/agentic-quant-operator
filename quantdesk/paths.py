"""Where everything lives. One place, so nothing has to guess."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CONFIG = ROOT / "config"
EVIDENCE = ROOT / "evidence"
RUNTIME = ROOT / "runtime"  # mutable state; gitignored

SANDBOX_FILE = CONFIG / "sandbox.json"
POLICY_FILE = CONFIG / "policy.json"
FREEZE_FILE = CONFIG / "freeze.json"

REGISTRY_FILE = EVIDENCE / "registry.json"
VERDICT_DIR = EVIDENCE / "verdicts"
LEDGER_DIR = EVIDENCE / "ledgers"

TRADING_PAUSED_FLAG = RUNTIME / "TRADING_PAUSED"
CYCLE_LOG = RUNTIME / "cycles.jsonl"


def ensure_runtime() -> Path:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    return RUNTIME
