"""Forward-evaluation metrics.

The bootstrap tests matter most: the clustered version has to be *wider* than
the naive one on correlated data, because that widening is the whole reason it
exists.
"""

import math
import unittest

from quantdesk import metrics


class BrierTest(unittest.TestCase):
    def test_perfect_forecast_scores_zero(self):
        self.assertEqual(metrics.brier([1.0, 0.0], [1, 0]), 0.0)

    def test_coin_flip_scores_a_quarter(self):
        self.assertAlmostEqual(metrics.brier([0.5] * 4, [1, 0, 1, 0]), 0.25)

    def test_skill_is_positive_when_the_model_wins(self):
        skill = metrics.brier_skill([0.9, 0.1], [0.6, 0.4], [1, 0])
        self.assertGreater(skill, 0)

    def test_skill_is_negative_when_the_market_wins(self):
        skill = metrics.brier_skill([0.6, 0.4], [0.9, 0.1], [1, 0])
        self.assertLess(skill, 0)

    def test_skill_against_itself_is_zero(self):
        probs = [0.7, 0.3, 0.55]
        self.assertAlmostEqual(metrics.brier_skill(probs, probs, [1, 0, 1]), 0.0)

    def test_mismatched_lengths_raise(self):
        with self.assertRaises(ValueError):
            metrics.brier([0.5], [1, 0])

    def test_out_of_range_probability_raises(self):
        with self.assertRaises(ValueError):
            metrics.brier([1.5], [1])

    def test_empty_input_raises(self):
        with self.assertRaises(ValueError):
            metrics.brier([], [])


class CalibrationTest(unittest.TestCase):
    def test_perfectly_calibrated_has_zero_ece(self):
        # 70% stated, 70 of 100 happen.
        probs = [0.7] * 100
        outcomes = [1] * 70 + [0] * 30
        self.assertAlmostEqual(metrics.ece(probs, outcomes), 0.0, places=9)

    def test_overconfident_forecaster_has_positive_ece(self):
        probs = [0.95] * 100
        outcomes = [1] * 60 + [0] * 40
        self.assertAlmostEqual(metrics.ece(probs, outcomes), 0.35, places=9)

    def test_probability_of_one_lands_in_the_top_bin(self):
        table = metrics.reliability_table([1.0], [1], bins=10)
        self.assertEqual(table[0]["bin_hi"], 1.0)

    def test_reliability_table_reports_every_non_empty_bin(self):
        table = metrics.reliability_table([0.05, 0.15, 0.95], [0, 0, 1], bins=10)
        self.assertEqual(len(table), 3)
        self.assertEqual(sum(row["n"] for row in table), 3)


class ClvTest(unittest.TestCase):
    def test_yes_gains_when_the_price_rises(self):
        self.assertAlmostEqual(metrics.clv_bps(0.40, 0.45, "YES"), 500.0)

    def test_no_gains_when_the_price_falls(self):
        self.assertAlmostEqual(metrics.clv_bps(0.40, 0.35, "NO"), 500.0)

    def test_no_loses_when_the_price_rises(self):
        self.assertAlmostEqual(metrics.clv_bps(0.40, 0.45, "NO"), -500.0)

    def test_price_outside_zero_one_raises(self):
        with self.assertRaises(ValueError):
            metrics.clv_bps(1.4, 0.5)

    def test_unknown_side_raises(self):
        with self.assertRaises(ValueError):
            metrics.clv_bps(0.4, 0.5, "MAYBE")


class ClusteredBootstrapTest(unittest.TestCase):
    def test_clustering_widens_the_interval_on_correlated_data(self):
        """Ten days, twenty identical bets each: 200 rows, 10 real samples.

        Treating the rows as independent shrinks the interval by roughly the
        square root of the cluster size, which is exactly the error that turns
        a coin flip into a publishable edge.
        """
        values, days = [], []
        for day in range(10):
            level = 100.0 if day % 2 else -80.0  # each day moves together
            values.extend([level] * 20)
            days.extend([day] * 20)

        clustered = metrics.clustered_bootstrap_ci(values, days, n_boot=2000, seed=1)
        naive = metrics.clustered_bootstrap_ci(values, range(len(values)), n_boot=2000, seed=1)

        self.assertEqual(clustered["n_clusters"], 10)
        self.assertEqual(naive["n_clusters"], 200)
        self.assertGreater(
            clustered["hi"] - clustered["lo"],
            (naive["hi"] - naive["lo"]) * 2,
        )

    def test_a_clear_effect_is_significant(self):
        values = [50.0 + (i % 3) for i in range(60)]
        ci = metrics.clustered_bootstrap_ci(values, [i // 3 for i in range(60)], n_boot=2000)
        self.assertTrue(ci["significant"])
        self.assertGreater(ci["lo"], 0)

    def test_noise_around_zero_is_not_significant(self):
        values = [(-1) ** i * 100.0 for i in range(60)]
        ci = metrics.clustered_bootstrap_ci(values, [i // 6 for i in range(60)], n_boot=2000)
        self.assertFalse(ci["significant"])

    def test_the_reported_mean_is_the_observed_mean_not_a_bootstrap_mean(self):
        values = [1.0, 2.0, 3.0, 4.0]
        ci = metrics.clustered_bootstrap_ci(values, [0, 0, 1, 1], n_boot=500)
        self.assertAlmostEqual(ci["mean"], 2.5)

    def test_it_is_deterministic_under_a_seed(self):
        args = ([1.0, -2.0, 3.0, 0.5], [0, 0, 1, 1])
        a = metrics.clustered_bootstrap_ci(*args, n_boot=500, seed=7)
        b = metrics.clustered_bootstrap_ci(*args, n_boot=500, seed=7)
        self.assertEqual(a, b)

    def test_mismatched_lengths_raise(self):
        with self.assertRaises(ValueError):
            metrics.clustered_bootstrap_ci([1.0, 2.0], [0])


class LogLossTest(unittest.TestCase):
    def test_confident_and_wrong_is_punished(self):
        self.assertGreater(metrics.log_loss([0.001], [1]), metrics.log_loss([0.4], [1]))

    def test_certainty_does_not_produce_infinity(self):
        self.assertTrue(math.isfinite(metrics.log_loss([1.0, 0.0], [0, 1])))


if __name__ == "__main__":
    unittest.main()
