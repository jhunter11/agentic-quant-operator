"""Terminal formatting. Small on purpose.

Colour is an accent, never the thing carrying the meaning — every line reads
the same piped to a file, on a light terminal, or on a monochrome one. Honours
``NO_COLOR`` and switches off automatically when stdout is not a terminal.
"""

from __future__ import annotations

import os
import shutil
import sys
import textwrap

WIDTH = min(shutil.get_terminal_size((84, 24)).columns, 84)

_ON = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _ON else s


def dim(s: str) -> str:
    return _c("2", s)


def bold(s: str) -> str:
    return _c("1", s)


def green(s: str) -> str:
    return _c("32", s)


def red(s: str) -> str:
    return _c("31", s)


def cyan(s: str) -> str:
    return _c("36", s)


def header(title: str) -> None:
    print()
    print(bold(title))
    print(dim("─" * min(len(title), WIDTH)))


def rule(label: str = "") -> None:
    if not label:
        print(dim("─" * (WIDTH - 2)))
        return
    print(dim(f"── {label} " + "─" * max(WIDTH - len(label) - 6, 2)))


def note(text: str) -> None:
    for line in textwrap.wrap(text, WIDTH - 2):
        print(dim(line))


def bullet(text: str) -> None:
    lines = textwrap.wrap(text, WIDTH - 6)
    for i, line in enumerate(lines):
        print(f"  {'·' if i == 0 else ' '} {line}")


def verdict(ok: bool, label: str, reason: str = "") -> None:
    """One outcome line: a mark, what was attempted, and what came back."""
    mark = green("  ✓ ALLOWED") if ok else red("  ✗ REFUSED")
    print(f"{mark}  {label}")
    if reason:
        for line in textwrap.wrap(reason, WIDTH - 16):
            print(f"             {dim(line)}")


def kv(key: str, value: str, width: int = 22) -> None:
    print(f"  {key:<{width}} {value}")
