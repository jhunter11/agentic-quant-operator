#!/usr/bin/env python3
"""Render the agent architecture diagram -> assets/architecture.png
Run: python3 assets/make_architecture.py"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

HERE = os.path.dirname(os.path.abspath(__file__))
fig, ax = plt.subplots(figsize=(12, 9))
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

CY = "#9ae6b4"; GATE = "#fed7d7"; FROZ = "#cbd5e0"; SUP = "#bee3f8"; OUT = "#d6bcfa"


def box(x, y, w, h, t, c, bold=False, fs=10):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5,rounding_size=2",
                                fc=c, ec="#2d3748", lw=1.3))
    ax.text(x + w/2, y + h/2, t, ha="center", va="center",
            fontsize=fs, fontweight="bold" if bold else "normal")


def arr(x1, y1, x2, y2, color="#2d3748", style="-", lw=1.6):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=15,
                 color=color, lw=lw, linestyle=style, shrinkA=3, shrinkB=3))


ax.text(50, 97, "Agentic Quant Operator — control loop & guardrails", ha="center",
        fontsize=15, fontweight="bold")

# Frozen control plane banner
box(8, 86, 84, 7, "FROZEN CONTROL PLANE  (agent cannot edit — tampering is detectable)\n"
    "mission · budget · spend gate · review panel · safety rails", FROZ, bold=True, fs=9.5)

# Scheduler (left)
box(2, 50, 22, 16, "Scheduler\n\nratelimit_guard\nchain-dispatch\n+ self-healing\nwatchdogs", SUP, fs=9)

# Knowledge/memory (left-bottom)
box(2, 24, 22, 16, "Knowledge\n\ngraph (graphify)\nObsidian vault\nmemory vault\n(pull-based)", SUP, fs=9)

# The work-cycle (center, as a loop of 5)
cx = [55, 74, 67, 43, 36]
cy = [74, 60, 38, 38, 60]
labels = ["SENSE", "ORIENT", "ACT", "THINK→plan", "(stage)"]
# Use clear 5-step loop
nodes = [("SENSE", 45, 74), ("ORIENT", 68, 70), ("THINK", 74, 50),
         ("ACT", 57, 35), ("REFLECT", 38, 50)]
for name, x, y in nodes:
    box(x-8, y-5, 16, 10, name, CY, bold=True, fs=10.5)
# loop arrows
order = [(45, 74, 68, 70), (68, 70, 74, 50), (74, 50, 57, 35),
         (57, 35, 38, 50), (38, 50, 45, 74)]
for x1, y1, x2, y2 in order:
    arr(x1+6, y1, x2-6, y2)
ax.text(56, 55, "one action\nper cycle", ha="center", va="center", fontsize=8.5,
        style="italic", color="#555")

# Scheduler feeds SENSE; knowledge feeds SENSE
arr(24, 60, 37, 73)
arr(24, 34, 35, 68, style="--")

# ACT must pass the gates (bottom)
box(8, 6, 26, 11, "spend.py\nMONEY GATE\n(hard cap, no self-widen)", GATE, fs=9)
box(37, 6, 26, 11, "panel.py\nRED/BLUE REVIEW\n(tamper-evident verdict)", GATE, fs=9)
box(66, 6, 26, 11, "factory.py\nPROMOTION GATE\n(CLV · Brier · calibration)", GATE, fs=9)
arr(52, 35, 21, 17)
arr(57, 35, 50, 17)
arr(62, 35, 79, 17)
ax.text(50, 21, "every consequential ACT is gated", ha="center", fontsize=8.5,
        style="italic", color="#c53030")

# Output (right)
box(80, 44, 18, 22, "OUTPUT\n\nvalidated\nstrategies,\npaper P&L,\nthe modeling\nsystem", OUT, fs=9)
arr(73, 50, 80, 52)

fig.tight_layout()
out = os.path.join(HERE, "architecture.png")
fig.savefig(out, dpi=140, bbox_inches="tight")
print("wrote", out)
