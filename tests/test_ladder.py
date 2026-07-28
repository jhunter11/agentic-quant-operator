"""The promotion gate — the thing standing between a strategy and capital."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from quantdesk import ladder

PASSING = {
    "provenance": "ledger",
    "n_settlements": 240,
    "n_independent_days": 31,
    "clv_bps": 48.0,
    "clv_significant": True,
    "paper_pnl": 310.0,
    "ece": 0.021,
    "beats_market_baseline": True,
}


def candidate(stage="PAPER", **metric_overrides):
    m = dict(PASSING)
    m.update(metric_overrides)
    return {"id": "cand", "stage": stage, "metrics": m}


def write_verdict(directory, strategy, *, proceed=True, age_hours=0.0):
    directory.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    path = directory / f"verdict-{ts.strftime('%Y%m%dT%H%M%SZ')}-deadbeef.json"
    path.write_text(json.dumps({
        "ts": ts.isoformat(),
        "strategy": strategy,
        "brief": "brief",
        "brief_sha256": "deadbeef",
        "verdict": "PROCEED" if proceed else "BLOCKED",
        "verdict_line": "VERDICT: PROCEED" if proceed else "VERDICT: BLOCKED — no",
        "rationale_tail": "",
    }))
    return path


class AdjudicationTest(unittest.TestCase):
    def setUp(self):
        self.policy = ladder.load_policy()

    def test_full_evidence_reaches_ready(self):
        self.assertEqual(ladder.adjudicate(candidate(), self.policy).action, "READY")

    def test_too_few_settlements_holds(self):
        r = ladder.adjudicate(candidate(n_settlements=19), self.policy)
        self.assertEqual(r.action, "HOLD")
        self.assertIn("settlements 19/20", r.reason)

    def test_correlated_sample_holds_even_with_many_rows(self):
        """1,000 decisions across 3 days is 3 samples, not 1,000."""
        r = ladder.adjudicate(candidate(n_settlements=1000, n_independent_days=3), self.policy)
        self.assertEqual(r.action, "HOLD")
        self.assertIn("independent days 3/15", r.reason)

    def test_positive_but_insignificant_clv_holds(self):
        r = ladder.adjudicate(candidate(clv_significant=False), self.policy)
        self.assertEqual(r.action, "HOLD")
        self.assertIn("CLV", r.reason)

    def test_unmeasured_clv_is_not_treated_as_zero(self):
        r = ladder.adjudicate(candidate(clv_bps=None, clv_significant=False), self.policy)
        self.assertEqual(r.action, "HOLD")
        self.assertIn("not measured", r.reason)

    def test_hand_typed_metrics_cannot_clear_the_gate(self):
        """The single most valuable rule here: numbers must be derived."""
        r = ladder.adjudicate(candidate(provenance="manual"), self.policy)
        self.assertEqual(r.action, "HOLD")
        self.assertIn("provenance", r.reason)

    def test_decalibrated_is_retired_not_held(self):
        r = ladder.adjudicate(candidate(decalibrated=True), self.policy)
        self.assertEqual(r.action, "RETIRE")

    def test_significant_negative_pnl_is_retired(self):
        r = ladder.adjudicate(
            candidate(paper_pnl=-120.0, paper_pnl_significant=True), self.policy)
        self.assertEqual(r.action, "RETIRE")

    def test_research_needs_a_baseline_win(self):
        s = {"id": "c", "stage": "RESEARCH", "metrics": {"oos_beats_baseline": False}}
        self.assertEqual(ladder.adjudicate(s, self.policy).action, "HOLD")

    def test_research_that_wins_and_calibrates_goes_to_paper(self):
        s = {"id": "c", "stage": "RESEARCH",
             "metrics": {"oos_beats_baseline": True, "ece": 0.01}}
        self.assertEqual(ladder.adjudicate(s, self.policy).action, "PAPER")

    def test_adjudication_does_not_mutate(self):
        s = candidate()
        before = json.dumps(s, sort_keys=True)
        ladder.adjudicate(s, self.policy)
        self.assertEqual(before, json.dumps(s, sort_keys=True))


class PromotionTest(unittest.TestCase):
    def setUp(self):
        self.policy = ladder.load_policy()
        self.tmp = Path(tempfile.mkdtemp(prefix="ladder-test-"))
        self.verdicts = self.tmp / "verdicts"
        self.verdicts.mkdir()

    def promote(self, s, to, **kw):
        return ladder.promote(s, to, policy=self.policy, verdict_dirs=(self.verdicts,), **kw)

    def test_cannot_skip_a_rung(self):
        r = self.promote(candidate(), "LIVE")
        self.assertEqual(r.action, "BLOCKED")
        self.assertIn("skips a rung", r.reason)

    def test_ready_without_a_verdict_is_blocked(self):
        r = self.promote(candidate(), "READY")
        self.assertEqual(r.action, "BLOCKED")
        self.assertIn("no PROCEED artifact", r.reason)

    def test_ready_with_a_fresh_verdict_succeeds(self):
        write_verdict(self.verdicts, "cand")
        s = candidate()
        r = self.promote(s, "READY")
        self.assertEqual(r.action, "READY")
        self.assertEqual(s["stage"], "READY")

    def test_a_stale_verdict_does_not_count(self):
        write_verdict(self.verdicts, "cand", age_hours=48)
        self.assertEqual(self.promote(candidate(), "READY").action, "BLOCKED")

    def test_a_verdict_for_another_strategy_does_not_count(self):
        write_verdict(self.verdicts, "some_other_strategy")
        self.assertEqual(self.promote(candidate(), "READY").action, "BLOCKED")

    def test_a_blocked_verdict_does_not_count(self):
        write_verdict(self.verdicts, "cand", proceed=False)
        self.assertEqual(self.promote(candidate(), "READY").action, "BLOCKED")

    def test_weak_evidence_is_blocked_even_with_a_verdict(self):
        write_verdict(self.verdicts, "cand")
        r = self.promote(candidate(n_settlements=5), "READY")
        self.assertEqual(r.action, "BLOCKED")
        self.assertIn("evidence does not support", r.reason)

    def test_live_needs_a_worst_case_figure(self):
        write_verdict(self.verdicts, "cand")
        r = self.promote(candidate(stage="READY"), "LIVE")
        self.assertEqual(r.action, "BLOCKED")
        self.assertIn("worst-case", r.reason)

    def test_live_is_blocked_when_the_spend_gate_refuses(self):
        write_verdict(self.verdicts, "cand")
        r = self.promote(candidate(stage="READY"), "LIVE",
                         worst_case_usd=1_000_000.0, commit_spend=False)
        self.assertEqual(r.action, "BLOCKED")
        self.assertIn("spend gate refused", r.reason)

    def test_a_blocked_promotion_leaves_the_stage_alone(self):
        s = candidate()
        self.promote(s, "READY")
        self.assertEqual(s["stage"], "PAPER")

    def test_a_successful_promotion_is_written_to_history(self):
        write_verdict(self.verdicts, "cand")
        s = candidate()
        self.promote(s, "READY")
        self.assertIn("PAPER -> READY", s["history"][-1]["event"])


class RealRegistryTest(unittest.TestCase):
    """The registry shipped in evidence/ is the actual end state of the run."""

    def setUp(self):
        self.strategies = ladder.load_registry()

    def test_thirty_four_candidates_were_tracked(self):
        self.assertEqual(len(self.strategies), 34)

    def test_fourteen_were_retired(self):
        retired = [s for s in self.strategies if s["stage"] == "RETIRED"]
        self.assertEqual(len(retired), 14)

    def test_none_ever_reached_live(self):
        self.assertEqual([s for s in self.strategies if s["stage"] == "LIVE"], [])

    def test_every_stage_change_is_recorded(self):
        for s in self.strategies:
            self.assertTrue(s["history"], f"{s['id']} has no history")

    def test_no_candidate_in_the_registry_clears_the_paper_gate_today(self):
        policy = ladder.load_policy()
        for s in self.strategies:
            if s["stage"] == "PAPER":
                self.assertNotEqual(ladder.adjudicate(s, policy).action, "READY")


if __name__ == "__main__":
    unittest.main()
