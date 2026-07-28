"""The frozen control plane."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from quantdesk import integrity
from quantdesk.paths import ROOT


class LiveRepoTest(unittest.TestCase):
    def test_the_checked_in_control_plane_is_intact(self):
        """If this fails, someone changed a guardrail without re-blessing it."""
        result = integrity.verify()
        self.assertTrue(result.intact, str(result))

    def test_the_manifest_covers_every_frozen_file(self):
        manifest = json.loads((ROOT / "config" / "freeze.json").read_text())["files"]
        self.assertEqual(sorted(manifest), sorted(integrity.FROZEN))

    def test_the_gates_are_all_frozen(self):
        for module in ("sandbox", "panel", "ladder", "metrics", "integrity"):
            self.assertIn(f"quantdesk/{module}.py", integrity.FROZEN)

    def test_the_policy_and_the_cap_are_frozen(self):
        self.assertIn("config/policy.json", integrity.FROZEN)
        self.assertIn("config/sandbox.json", integrity.FROZEN)


class DriftTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="integrity-test-"))
        for rel in integrity.FROZEN:
            dst = self.tmp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / rel, dst)
        self.manifest = self.tmp / "freeze.json"
        integrity.rebless(manifest_file=self.manifest, root=self.tmp)

    def verify(self):
        return integrity.verify(manifest_file=self.manifest, root=self.tmp)

    def test_an_untouched_copy_verifies(self):
        self.assertTrue(self.verify().intact)

    def test_a_one_byte_edit_is_caught(self):
        target = self.tmp / "quantdesk" / "sandbox.py"
        target.write_text(target.read_text() + " ")
        result = self.verify()
        self.assertFalse(result.intact)
        self.assertEqual(result.drifted, ["quantdesk/sandbox.py"])

    def test_lowering_a_gate_is_caught(self):
        policy = self.tmp / "config" / "policy.json"
        raw = json.loads(policy.read_text())
        raw["paper"]["min_settlements"] = 1
        policy.write_text(json.dumps(raw, indent=2))
        self.assertIn("config/policy.json", self.verify().drifted)

    def test_raising_the_cap_is_caught(self):
        box = self.tmp / "config" / "sandbox.json"
        raw = json.loads(box.read_text())
        raw["limit_usd"] = 10_000.0
        box.write_text(json.dumps(raw, indent=2))
        self.assertIn("config/sandbox.json", self.verify().drifted)

    def test_deleting_a_frozen_file_is_caught(self):
        (self.tmp / "quantdesk" / "panel.py").unlink()
        result = self.verify()
        self.assertFalse(result.intact)
        self.assertEqual(result.missing, ["quantdesk/panel.py"])

    def test_a_missing_manifest_fails_closed(self):
        self.manifest.unlink()
        self.assertFalse(self.verify().intact)

    def test_a_corrupt_manifest_fails_closed(self):
        self.manifest.write_text("{ not json")
        self.assertFalse(self.verify().intact)

    def test_reblessing_clears_the_drift(self):
        """Which is the point: covering your tracks requires a manifest commit."""
        target = self.tmp / "quantdesk" / "sandbox.py"
        target.write_text(target.read_text() + " ")
        self.assertFalse(self.verify().intact)
        integrity.rebless(manifest_file=self.manifest, root=self.tmp)
        self.assertTrue(self.verify().intact)


if __name__ == "__main__":
    unittest.main()
