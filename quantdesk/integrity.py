"""The frozen control plane — the files the agent is not allowed to edit.

An autonomous agent that can rewrite its own limits has no limits. So the
files that define the limits — the mission, the spend gate, the review panel,
the promotion policy, this module — are hashed into ``config/freeze.json``,
and :func:`verify` re-checks them.

The freeze does not *prevent* an edit; a process that can write ``policy.json``
can write it. What it guarantees is that an edit **cannot be quiet**. Drift is
detected on the next check, the check runs before every consequential action,
and the manifest itself is committed to git — so even regenerating the manifest
to cover your tracks shows up as a diff in review.

This is the mechanism that caught the real incident preserved in
``evidence/verdicts/verdict-20260612T031724Z-72f39fbf.json``: the agent had
raised its own sandbox cap from $7 to $10 by back-dating an entry in the
funding history. The freeze check failed, the review panel saw the failure,
and the proposed live order was BLOCKED.

Regenerating the manifest is an **operator** action, performed after reviewing
a written proposal — never something the agent does for itself::

    python -m quantdesk.integrity --check     # verify (this is what the loop runs)
    python -m quantdesk.integrity --rebless   # operator: bless the current state
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field

from .paths import FREEZE_FILE, ROOT

__all__ = ["FrozenPlane", "verify", "rebless", "FROZEN"]

#: Files that define the agent's authority. Editing any of these is a change to
#: what the agent is *allowed to do*, not merely to what it does.
FROZEN = [
    "config/policy.json",
    "config/sandbox.json",
    "quantdesk/sandbox.py",
    "quantdesk/integrity.py",
    "quantdesk/panel.py",
    "quantdesk/ladder.py",
    "quantdesk/metrics.py",
    "docs/MISSION.md",
]


@dataclass(frozen=True)
class FrozenPlane:
    intact: bool
    checked: int
    drifted: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.intact:
            return f"frozen control plane intact ({self.checked} files)"
        parts = []
        if self.drifted:
            parts.append("modified: " + ", ".join(self.drifted))
        if self.missing:
            parts.append("missing: " + ", ".join(self.missing))
        return "DRIFT — " + "; ".join(parts)


def sha256(path) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def verify(*, manifest_file=None, root=None) -> FrozenPlane:
    """Compare every frozen file against the blessed manifest."""
    manifest_file = manifest_file or FREEZE_FILE
    root = root or ROOT
    try:
        with open(manifest_file) as fh:
            manifest = json.load(fh)["files"]
    except (OSError, KeyError, json.JSONDecodeError):
        return FrozenPlane(intact=False, checked=0, missing=[str(manifest_file)])

    drifted, missing = [], []
    for rel, expected in sorted(manifest.items()):
        path = root / rel
        if not path.exists():
            missing.append(rel)
        elif sha256(path) != expected:
            drifted.append(rel)

    return FrozenPlane(
        intact=not drifted and not missing,
        checked=len(manifest),
        drifted=drifted,
        missing=missing,
    )


def rebless(*, manifest_file=None, root=None) -> int:
    """OPERATOR ONLY — rewrite the manifest to bless the current file contents.

    The agent must never call this. It is how a reviewed change to the control
    plane becomes the new baseline, and it is meant to be a deliberate human
    act with a git diff attached.
    """
    manifest_file = manifest_file or FREEZE_FILE
    root = root or ROOT
    files = {}
    for rel in FROZEN:
        path = root / rel
        if path.exists():
            files[rel] = sha256(path)
        else:
            print(f"skip (missing): {rel}")
    with open(manifest_file, "w") as fh:
        json.dump(
            {
                "_doc": "Operator-blessed hashes of the frozen control plane. "
                        "Verified by quantdesk.integrity.verify() before every "
                        "consequential action. Regenerate ONLY via --rebless, "
                        "after reviewing a written proposal.",
                "files": files,
            },
            fh,
            indent=2,
        )
        fh.write("\n")
    return len(files)


def main(argv: list[str]) -> int:
    if "--rebless" in argv:
        n = rebless()
        print(f"blessed {n} files -> {FREEZE_FILE.relative_to(ROOT)}")
        return 0
    result = verify()
    print(result)
    return 0 if result.intact else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
