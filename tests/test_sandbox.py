"""The money gate. Every test here is an attempt to get a dollar it shouldn't."""

import json
import math
import tempfile
import unittest
from pathlib import Path

from quantdesk import killswitch, sandbox


class SandboxTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sandbox-test-"))
        self.box = self.tmp / "sandbox.json"
        self.flag = self.tmp / "TRADING_PAUSED"
        self.box.write_text(json.dumps({"limit_usd": 10.0, "spent_usd": 0.0, "ledger": []}))

    def ask(self, amount, reason="test", **kw):
        return sandbox.request(amount, reason, sandbox_file=self.box, paused_flag=self.flag, **kw)

    # -- the ordinary path ------------------------------------------------

    def test_spend_within_cap_is_approved(self):
        d = self.ask(4.00)
        self.assertTrue(d.approved)
        self.assertEqual(d.remaining_usd, 6.00)

    def test_spend_is_durable_across_calls(self):
        """The cap has to survive a process restart, or crashing resets the budget."""
        self.ask(6.00)
        self.assertEqual(json.loads(self.box.read_text())["spent_usd"], 6.00)
        self.assertFalse(self.ask(5.00).approved)

    def test_every_spend_lands_in_the_ledger(self):
        self.ask(1.00, "data feed")
        entry = json.loads(self.box.read_text())["ledger"][-1]
        self.assertEqual(entry["amount_usd"], 1.00)
        self.assertEqual(entry["reason"], "data feed")
        self.assertEqual(entry["remaining_after_usd"], 9.00)

    # -- the refusals -----------------------------------------------------

    def test_over_cap_is_denied(self):
        self.assertFalse(self.ask(10.01).approved)

    def test_exactly_the_cap_is_allowed(self):
        self.assertTrue(self.ask(10.00).approved)
        self.assertFalse(self.ask(0.01).approved)

    def test_nan_is_denied(self):
        """nan > x is False for every x, so a naive bound check approves it."""
        d = self.ask(float("nan"))
        self.assertFalse(d.approved)
        self.assertIn("finite", d.reason)

    def test_infinity_is_denied(self):
        self.assertFalse(self.ask(float("inf")).approved)

    def test_zero_is_denied(self):
        """A $0 spend must not mint an APPROVED receipt to wave at a later gate."""
        self.assertFalse(self.ask(0.0).approved)

    def test_negative_is_denied(self):
        """Otherwise the agent refunds itself headroom."""
        self.assertFalse(self.ask(-50.0).approved)
        self.assertEqual(json.loads(self.box.read_text())["spent_usd"], 0.0)

    def test_non_numeric_is_denied(self):
        self.assertFalse(self.ask("nine dollars").approved)

    def test_reason_is_required(self):
        self.assertFalse(self.ask(1.00, "   ").approved)

    def test_corrupt_state_fails_closed(self):
        self.box.write_text(json.dumps({"limit_usd": -1.0, "spent_usd": 0.0}))
        d = self.ask(1.00)
        self.assertFalse(d.approved)
        self.assertIn("corrupt", d.reason)

    def test_paused_denies_everything(self):
        killswitch.pause("test", flag=self.flag)
        self.assertFalse(self.ask(0.01).approved)
        killswitch.resume(flag=self.flag)
        self.assertTrue(self.ask(0.01).approved)

    # -- the structural guarantee -----------------------------------------

    def test_no_code_path_widens_the_cap(self):
        """The gate can raise spent_usd. Nothing in it may raise limit_usd."""
        for amount in (1.0, 2.5, 99.0, -3.0, 0.0, float("nan")):
            self.ask(amount)
        self.assertEqual(json.loads(self.box.read_text())["limit_usd"], 10.0)

    def test_require_raises_instead_of_returning(self):
        with self.assertRaises(sandbox.SpendDenied):
            sandbox.require(99.0, "too much", sandbox_file=self.box, paused_flag=self.flag)

    def test_dry_run_does_not_commit(self):
        self.assertTrue(self.ask(4.00, commit=False).approved)
        self.assertEqual(json.loads(self.box.read_text())["spent_usd"], 0.0)

    def test_status_reports_headroom(self):
        self.ask(3.00)
        st = sandbox.status(sandbox_file=self.box, paused_flag=self.flag)
        self.assertEqual(st["remaining_usd"], 7.00)
        self.assertEqual(st["n_spends"], 1)
        self.assertFalse(st["paused"])

    def test_rounding_cannot_leak_a_cent(self):
        for _ in range(3):
            self.assertTrue(self.ask(3.33).approved)
        self.assertTrue(math.isclose(
            sandbox.status(sandbox_file=self.box, paused_flag=self.flag)["remaining_usd"],
            0.01, abs_tol=1e-9))
        self.assertFalse(self.ask(0.02).approved)


if __name__ == "__main__":
    unittest.main()
