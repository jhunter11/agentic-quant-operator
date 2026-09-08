# Evidence

This directory contains the registry, paper ledgers, and review artifacts preserved for the public research archive. Run `python -m quantdesk.score` to recompute the ledger metrics. The files support analysis of the included sample, without establishing a profitable strategy.

## Candidate registry

`registry.json` contains 34 candidates and their recorded stage histories. The final stage counts are:

| Stage | Count |
| --- | ---: |
| `BACKLOG` | 16 |
| `RESEARCH` | 3 |
| `PAPER` | 1 |
| `RETIRED` | 14 |
| `READY` or `LIVE` | 0 |

Retirement reasons sometimes refer to numbered entries in a private log of discarded ideas. Those references retain their original context. The private log is outside this release.

## Paper ledgers

The ledgers contain one row per recorded decision. Fields include model probability, entry price, outcome, fee, stake, and PnL. The public export alone does not independently prove when each source observation was first recorded.

| File | Settled rows | Recorded days | Closing quotes |
| --- | ---: | ---: | --- |
| `worldcup_paper.jsonl` | 43 | 10 | Available |
| `mlb_kprop_paper.jsonl` | 1,364 | 12 | Missing |

The scoring code uses entry price as the market forecasting baseline. Market prices can reflect fees, spread, liquidity, and other frictions, so that baseline is an empirical comparison rather than a probability guarantee.

The MLB export omits an earlier field that contained zeros or nulls when closing-quote capture had not populated. The scorer returns missing closing-line value. It must not interpret the absent observations as flat price movement.

The historical source also marked repairs to settlement joins that had produced incorrect apparent profit. Those repairs limit how much confidence to place in an unverified source export. Reconcile instrument identifiers and outcomes before reusing the data.

## Review records

Eight artifacts contain three `PROCEED` and five `BLOCKED` verdicts. Each includes a brief hash and a recorded timestamp. These local JSON files are review records, without cryptographic authentication of their author or storage history.

| Time, UTC | Verdict | Recorded event |
| --- | --- | --- |
| June 12, 03:17 | `BLOCKED` | Control drift and a funding entry that raised the cap from $7 to $10 |
| June 12, 03:23 | `BLOCKED` | Reviewer unavailable |
| June 12, 03:26 | `BLOCKED` | Reviewer unavailable |
| June 12, 03:30 | `PROCEED` | Corrected control and funding records, with a new baseline |
| June 19, 09:13 | `BLOCKED` | Unparseable reviewer response |
| June 19, 09:14 | `BLOCKED` | Unparseable reviewer response |
| June 19, 09:16 | `PROCEED` | Proposed research direction changed to microstructure |
| June 19, 09:17 | `PROCEED` | Infrastructure self-test after the outage |

The cap-change incident remains in the archive. A later approved probe does not imply that a strategy passed the promotion gate.

## Export changes

The original export notes record replacements of home paths with `~` and truncation of reviewer transcripts to a verdict and rationale tail. They also record the omission of a later, unrelated verdict. Numerical ledger fields retain the values supplied in this export. This documentation review did not alter the registry, ledgers, or verdict files.
