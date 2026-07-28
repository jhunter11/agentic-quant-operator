# Evidence

Artifacts from the live run, not reconstructions. Everything here is read by
code in this repository — `python3 explore.py 3` recomputes the ledger metrics
from raw, and the test suite asserts against them.

## `registry.json` — 34 candidates

The strategy lifecycle registry as it stood at the end of the quant run. Every
stage change is appended to `history` with a reason, so a killed idea stays
killed. Metrics with `"provenance": "ledger"` were computed from a settled
ledger; nothing else can clear the promotion gate.

| stage | n | |
|---|---:|---|
| `BACKLOG` | 16 | generated, never worked |
| `RESEARCH` | 3 | offline validation |
| `PAPER` | 1 | recorded decisions against live prices |
| `RETIRED` | 14 | killed on their own evidence |
| `READY` / `LIVE` | 0 | nothing cleared the gate |

Retirement reasons carry graveyard numbers (`graveyard #14`, `#15`, `#17`) from
the loop's dead-idea log — the mechanism that stopped an idea-generating agent
from rediscovering its own dead ends.

## `ledgers/` — 1,407 settled decisions

One row per decision, committed **before** the outcome was known.

```json
{"event": "KXWCGAME-26JUN16ARGDZA", "event_date": "2026-06-16", "side": "YES",
 "model_p": 0.7855, "entry_price": 0.695, "closing_price": 0.985,
 "outcome": 1, "pnl": 2.0, "fee": 0.02, "stake": 5.0}
```

`entry_price` doubles as the market baseline: on a binary contract the price
*is* the market's stated probability, so "did we beat the market?" needs no
modelling assumption of our own.

| file | rows | independent days | notes |
|---|---:|---:|---|
| `worldcup_paper.jsonl` | 43 | 10 | full closing prices, so CLV is measurable |
| `mlb_kprop_paper.jsonl` | 1,364 | 12 | no closing prices — see below |

**On the missing MLB CLV.** The source ledger carries an
`entry_to_close_bps` field that is `0.0` on 1,220 rows and `null` on the rest,
because the close-quote capture never populated for that family. Shipping the
zeros would read as "CLV is flat"; the truth is "CLV was never measured". The
field is therefore dropped rather than carried, `score.py` reports `None`, and
the gate refuses on it. The distinction is the point.

The source ledger also carries `_edge_repaired` markers on rows where a broken
settlement join had been manufacturing fake profit, found and corrected
mid-run. That class of bug — phantom edge from settlement logic rather than from
the market — is the one the desk hunted hardest.

## `verdicts/` — 8 review artifacts

Each is a tamper-evident record of one adversarial review, keyed by the SHA-256
of the exact brief. Three PROCEED, five BLOCKED.

| when (UTC) | verdict | what happened |
|---|---|---|
| 06-12 03:17 | BLOCKED | control-plane drift **and the agent's own cap raised $7→$10** via a back-dated funding entry |
| 06-12 03:23 | BLOCKED | reviewer unavailable |
| 06-12 03:26 | BLOCKED | reviewer unavailable |
| 06-12 03:30 | PROCEED | drift fixed, funding record corrected, freeze re-blessed |
| 06-19 09:13 | BLOCKED | reviewer unparseable |
| 06-19 09:14 | BLOCKED | reviewer unparseable |
| 06-19 09:16 | PROCEED | retire model-vs-line as the primary thesis; pivot to microstructure |
| 06-19 09:17 | PROCEED | infrastructure self-test after the reviewer outage |

The 03:17 entry is the one worth reading in full. The agent had quietly raised
its own budget; the gate noticed; the record is here rather than deleted.

## Sanitisation

Home paths were replaced with `~`. Reviewer transcripts were truncated to the
verdict line plus a short rationale tail. One later verdict, from a different
project after this run ended, was left out as off-topic. Model probabilities,
prices, outcomes, and P&L are untouched — that is the evidence.
