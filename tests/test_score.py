"""Scoring the real ledgers.

These are regression tests against reality: the ledgers in ``evidence/`` are
1,407 decisions that were actually committed before their outcomes were known,
and the numbers below are what falls out of them. If a change to
:mod:`quantdesk.metrics` moves these, the change is wrong or the claim in the
README is.

The published companion study reports the same figures from an entirely
separate implementation — World Cup Brier .157 model / .143 market, skill −0.10;
MLB k-prop .160 / .158, skill −0.02. Two independent paths to the same numbers
is the check that matters.
"""

import unittest

from quantdesk import ladder, score
from quantdesk.paths import LEDGER_DIR


class WorldCupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = score.load_ledger(LEDGER_DIR / "worldcup_paper.jsonl")
        cls.m = score.score_ledger(rows, n_boot=2_000, seed=0)

    def test_sample_size(self):
        self.assertEqual(self.m["n_settlements"], 43)
        self.assertEqual(self.m["n_independent_days"], 10)

    def test_it_lost_money(self):
        self.assertAlmostEqual(self.m["paper_pnl"], -15.87, places=2)

    def test_it_did_not_beat_the_market(self):
        self.assertAlmostEqual(self.m["brier_model"], 0.157, places=3)
        self.assertAlmostEqual(self.m["brier_market"], 0.143, places=3)
        self.assertAlmostEqual(self.m["skill_vs_market"], -0.101, places=3)
        self.assertFalse(self.m["beats_market_baseline"])

    def test_closing_line_value_is_positive_but_not_significant(self):
        """The whole argument for clustering, in one assertion.

        Mean CLV is +67 bps. Resampled by match day the interval is enormous
        and spans zero — 43 decisions over 10 days is 10 samples, not 43.
        """
        self.assertGreater(self.m["clv_bps"], 0)
        lo, hi = self.m["clv_ci"]
        self.assertLess(lo, 0)
        self.assertGreater(hi, 0)
        self.assertFalse(self.m["clv_significant"])
        self.assertEqual(self.m["n_clv_clusters"], 10)

    def test_the_gate_refuses_it(self):
        candidate = {"id": "worldcup", "stage": "PAPER", "metrics": self.m}
        ruling = ladder.adjudicate(candidate)
        self.assertEqual(ruling.action, "HOLD")
        self.assertIn("independent days 10/15", ruling.reason)


class MlbPropTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = score.load_ledger(LEDGER_DIR / "mlb_kprop_paper.jsonl")
        cls.m = score.score_ledger(rows, n_boot=2_000, seed=0)

    def test_sample_size(self):
        self.assertEqual(self.m["n_settlements"], 1364)
        self.assertEqual(self.m["n_independent_days"], 12)

    def test_it_made_money_and_still_fails(self):
        """Profitable and not promotable are not a contradiction.

        +$22.89 over 1,364 contracts, and the clustered interval for per-trade
        P&L spans zero. Twelve game days is not enough to tell this apart from
        luck, so it does not advance.
        """
        self.assertGreater(self.m["paper_pnl"], 0)
        self.assertFalse(self.m["paper_pnl_significant"])
        self.assertEqual(ladder.adjudicate(
            {"id": "mlb", "stage": "PAPER", "metrics": self.m}).action, "HOLD")

    def test_it_did_not_beat_the_market(self):
        self.assertAlmostEqual(self.m["brier_model"], 0.160, places=3)
        self.assertAlmostEqual(self.m["brier_market"], 0.158, places=3)
        self.assertLess(self.m["skill_vs_market"], 0)
        self.assertFalse(self.m["beats_market_baseline"])

    def test_unmeasured_clv_is_none_not_zero(self):
        """The close-quote capture never populated for this family. Reporting
        that as 0 bps would read as a flat result rather than a missing one."""
        self.assertIsNone(self.m["clv_bps"])
        self.assertEqual(self.m["n_clv"], 0)
        self.assertFalse(self.m["clv_significant"])


class ProvenanceTest(unittest.TestCase):
    def test_every_derived_block_is_marked_ledger(self):
        for name, m in score.score_all(n_boot=200).items():
            self.assertEqual(m["provenance"], "ledger", name)

    def test_both_ledgers_are_present(self):
        self.assertEqual(sorted(score.score_all(n_boot=200)),
                         ["mlb_kprop_paper", "worldcup_paper"])

    def test_no_ledger_in_the_pack_clears_the_gate(self):
        """The honest headline: 1,407 real decisions, nothing worth funding."""
        for name, m in score.score_all(n_boot=500).items():
            ruling = ladder.adjudicate({"id": name, "stage": "PAPER", "metrics": m})
            self.assertEqual(ruling.action, "HOLD", f"{name} unexpectedly cleared")


if __name__ == "__main__":
    unittest.main()
