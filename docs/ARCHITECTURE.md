# Architecture

This repository contains Python controls and records from a quantitative research workflow. The [README](../README.md) reports the included results. Machine-specific scheduling and live-order implementation are outside the public release.

## Operator and agent responsibilities

The recorded design reserves funding changes, binding commitments, and public or irreversible actions for the operator. A scheduled language-model process selects research work within that mandate. The controls below implement specific checks for callers that use them.

The [mission](MISSION.md) belongs to the frozen control files. Its wording records the original mandate. The documentation review does not change that mandate or regenerate the frozen manifest.

The surrounding scheduler used a sense, orient, think, act, and reflect cycle, with one selected action per cycle. That workflow made individual decisions easier to inspect. It did not bound the consequences of every action to a small or reversible change.

## Frozen control files

[`integrity.py`](../quantdesk/integrity.py) compares configured files against hashes in `config/freeze.json`. It reports missing files and mismatches when a caller invokes the check.

The check detects changes relative to that manifest. It does not prevent writes, authenticate a modified manifest, or intercept every consequential action. Its value depends on when callers check it and who can change the files and baseline.

A June 12, 2026 review found control drift and a funding record that raised the agent's cap. The [verdicts](../evidence/verdicts/) preserve that refusal and later corrections. Only an operator can approve a new control baseline under the recorded policy.

## Spending and pause checks

[`sandbox.py`](../quantdesk/sandbox.py) checks a requested amount against the remaining configured balance. It rejects non-finite, zero, negative, or excessive amounts, a missing reason, invalid recorded balances, and a pause flag.

Approved committed requests update a local JSON ledger through a temporary file and replacement. The module contains no function for raising the cap. These facts do not establish that every external spending path uses it, or that file replacement supplies isolation between concurrent writers.

[`killswitch.py`](../quantdesk/killswitch.py) manages the pause flag. A caller must consult that flag for it to stop an action.

## Review artifacts

[`panel.py`](../quantdesk/panel.py) invokes a configured reviewer and writes a verdict artifact. A missing process, timeout, or response without a verdict line produces a blocked record. The intended response protocol distinguishes `PROCEED` and `BLOCKED`.

Each artifact contains the brief, its SHA-256 hash, strategy identifier, timestamp, and result. The promotion lookup selects a recent `PROCEED` for the same strategy. It does not take a new brief hash as an argument or prove that an artifact cannot be forged.

The parser and local artifact store need their own security review before reuse in a different execution system. A prompt that labels a brief untrusted does not establish resistance to every instruction embedded in it.

## Strategy promotion

[`ladder.py`](../quantdesk/ladder.py) separates a recommendation from the function that changes a strategy stage. Promotion checks the configured sequence and the recommendation, with additional review and spending checks for later stages.

The paper-stage checks include:

- At least 20 settled decisions and 15 recorded day groups.
- Nonnegative fee-adjusted closing-line value with the significance flag set.
- Positive paper PnL and a passing market-baseline comparison.
- Calibration error within the configured ceiling when that value exists.
- A metrics record whose provenance field equals `ledger`.

The provenance field is a label that the gate reads. It does not independently authenticate the data or prove how another caller computed a supplied record. [`score.py`](../quantdesk/score.py) supplies a reproducible path from the committed ledgers to metrics.

`READY` and `LIVE` require a recent review artifact. A live-stage request also needs the spending check for its stated worst-case amount. The committed registry contains no strategy at either stage. Separate order-plumbing probes appear in the review archive.

## Measurement limits

[`metrics.py`](../quantdesk/metrics.py) calculates calibration, Brier scores, closing-line value, and bootstrap summaries. Day clusters address dependence between observations within a day. They do not prove independence across days, correct selection bias, or guarantee wider intervals in every sample.

Market prices form a forecasting baseline. Fees, spread, liquidity, and market frictions can separate those prices from underlying probabilities. Closing-line value describes movement relative to a quote and does not establish executable profit.

The included MLB records have no usable closing quotes, so their closing-line value is missing. The World Cup and MLB samples span 10 and 12 days respectively, below the policy's 15-day threshold. Four of the eight review artifacts record reviewer outages or unparseable replies.

## Components outside this release

The original workflow also used scheduled dispatch, model routing, watchdogs, note retrieval, and records of retired ideas. Their implementations are machine-specific and absent here. The public source supports inspection of the included controls and evidence, without reproducing the full unattended system.
