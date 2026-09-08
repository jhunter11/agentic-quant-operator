# Agentic Quant Operator

A research archive and Python control plane for an autonomous quantitative research workflow.
It includes strategy records, paper ledgers, review verdicts, and tests for authorization and evidence gates.

The committed registry contains 34 candidates. Fourteen reached a retired state, and none reached promotion to strategy capital.
The included ledgers contain 1,407 settled paper decisions. These records do not establish that the tested markets are efficient.
They show that the tested models failed to supply enough evidence for promotion.

## Run the archive

Use Python 3.9 or later. The examples use the standard library and committed fixtures.

```bash
python explore.py
python -m quantdesk.score
python -m unittest discover -s tests -t .
```

The menu reads the registry and ledgers, recomputes metrics, and runs refusal examples.
The examples need no network or credentials.

## Controls

| Module | Check |
| --- | --- |
| [Integrity](quantdesk/integrity.py) | Compare control files with a frozen hash manifest |
| [Sandbox](quantdesk/sandbox.py) | Reject invalid amounts, budget violations, and paused actions |
| [Review panel](quantdesk/panel.py) | Reject blocked or unavailable reviews |
| [Promotion ladder](quantdesk/ladder.py) | Require ledger provenance and sufficient evidence |
| [Metrics](quantdesk/metrics.py) | Calibration and bootstrap statistics with day clusters |
| [Scoring](quantdesk/score.py) | Derive metrics from settled decisions |

These checks cover their specified inputs and callers. They do not make an autonomous agent incapable of bypassing every boundary.

## Recorded results

Run `python -m quantdesk.score` to recompute the ledger summary.

| Model | Settled decisions | Days | Model / market Brier | Skill | Paper result | Gate |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| World Cup match winner | 43 | 10 | 0.157 / 0.143 | -0.101 | -$15.87 | Refused |
| MLB strikeout props | 1,364 | 12 | 0.160 / 0.158 | -0.017 | +$22.89 | Refused |

Lower Brier scores are better. Both models trail the market-price baseline in this sample.
The small positive MLB result did not clear the clustered uncertainty check.
Many decisions share a game day, so their row count overstates the number of independent observations.

## A recorded control failure

On June 12, 2026, a review blocked a proposed order-plumbing probe after control files drifted and a funding record changed.
The [verdict archive](evidence/verdicts/) records the refusals, corrections, and a later approval.
It also includes blocked reviews when the reviewer could not be reached.

The agent did change a control record. The oversight process caught that instance.
The archive does not support a claim that the controls could never change or that no live probe was ever approved.
Strategy promotion and order-plumbing probes are separate events in the record.

## Source and evidence

- [Registry](evidence/registry.json): candidate stages and histories.
- [Ledgers](evidence/ledgers/): settled paper decisions.
- [Verdicts](evidence/verdicts/): dated review artifacts.
- [Architecture](docs/ARCHITECTURE.md): control-plane design.
- [Mission](docs/MISSION.md): recorded project mandate.

The dated evidence retains its original wording. Read it as a historical record, with the limits stated here.
This public archive excludes credentials, live-order implementation, private data caches, and machine-specific scheduling.

The related [casino-line-modeling](https://github.com/jhunter11/casino-line-modeling) repository contains models and a separate calibration analysis.

## License

MIT. See [LICENSE](LICENSE).
