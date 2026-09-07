"""Sparkling mead by bottle-conditioning: priming sugar, the tax-class flag,
and the guardrail that a stabilized mead cannot carbonate.

The priming numbers are pinned against the researched formula (McGill 2006;
27 CFR 24.10 for the 0.392 g/100 mL still-wine line).
"""
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew import calc
from brew.server import Request, dispatch
from brew.store import Store

OWNER = {"gal": "6", "abv": "12", "og": "", "fg": "1.000", "yeast": "71B",
         "demand": "medium", "additions": "4", "name": "Session",
         "honey": "wildflower"}
RECORD = {"gal": "6", "id": "B-2026-003", "pitched_at": "2026-08-10T15:40",
          "volume_gal": "6", "honey_lb": "12", "water_gal": "5",
          "yeast_g": "10", "goferm_g": "12.5", "og": "1.075", "ph": "3.9"}


class PrimingMathTest(unittest.TestCase):
    def test_residual_falls_as_it_warms(self):
        self.assertEqual(calc.residual_co2_vols(40), 1.46)
        self.assertEqual(calc.residual_co2_vols(68), 0.86)
        self.assertGreater(calc.residual_co2_vols(40),
                           calc.residual_co2_vols(70))

    def test_priming_sugar_matches_the_formula(self):
        # 5 gal to 2.5 vol at 68 °F: residual 0.86, CO2 = (2.5−0.86)×1.969×
        # 18.925 = 61.1 g; honey (0.40 yield) = 152.8 g
        d = calc.priming_sugar(5, 2.5, 68, "honey")
        self.assertEqual(d["residual_vols"], 0.86)
        self.assertEqual(d["co2_g"], 61.1)
        self.assertEqual(d["grams"], 152.8)
        # table sugar (0.51 yield) needs less by weight
        self.assertEqual(calc.priming_sugar(5, 2.5, 68, "table sugar")["grams"],
                         119.8)

    def test_the_tax_class_line(self):
        self.assertEqual(calc.TTB_STILL_VOLS, 1.99)      # 0.392 g/100mL
        self.assertEqual(calc.co2_tax_class(1.8), "still")
        self.assertEqual(calc.co2_tax_class(2.5), "sparkling / carbonated")
        self.assertFalse(calc.priming_sugar(6, 1.8, 65)["over_still"])
        self.assertTrue(calc.priming_sugar(6, 2.5, 65)["over_still"])

    def test_no_sugar_needed_if_already_there(self):
        with self.assertRaisesRegex(ValueError, "no priming sugar"):
            calc.priming_sugar(5, 0.5, 68)


class SparklingTestCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-test-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)
        dispatch(Request("POST", "/recipes", {}, OWNER, (), self.store))
        dispatch(Request("POST", "/recipes/session/must", {}, RECORD, (),
                         self.store))
        self.store.add_reading("B-2026-003", "1.000", at="2026-08-28T09:00")
        self.store.add_reading("B-2026-003", "1.000", at="2026-09-02T09:00")
        self.store.record_racking("B-2026-003", "5.7", at="2026-09-03T09:00")

    def file(self):
        return json.loads(
            (self.root / "batches" / "B-2026-003.json").read_text())


class PrimingRecordTest(SparklingTestCase):
    def test_priming_records_the_sugar_and_tax_class(self):
        b, d = self.store.record_priming("B-2026-003", "2.5", "68", "honey",
                                         at="2026-09-04T09:00")
        pr = self.file()["primings"][0]
        self.assertEqual(pr["target_vols"], 2.5)
        self.assertEqual(pr["sugar"], "honey")
        self.assertEqual(pr["tax_class"], "sparkling / carbonated")
        self.assertTrue(calc.is_primed(b))

    def test_a_stabilized_mead_cannot_be_primed(self):
        self.store.record_stabilize("B-2026-003", "3.4")
        with self.assertRaisesRegex(ValueError, "cannot carbonate"):
            self.store.record_priming("B-2026-003", "2.5", "68")
        self.assertIsNone(self.file().get("primings"))
        # ...unless a fresh pitch is recorded
        self.store.record_priming("B-2026-003", "2.5", "68",
                                  override_reason="re-pitched EC-1118")
        self.assertEqual(self.file()["primings"][0]["override"],
                         "re-pitched EC-1118")

    def test_a_primed_mead_refuses_stabilizing(self):
        self.store.record_priming("B-2026-003", "2.5", "68")
        with self.assertRaisesRegex(ValueError, "never carbonate"):
            self.store.record_stabilize("B-2026-003", "3.4")

    def test_bottling_a_sparkling_mead_carries_the_tax_class(self):
        self.store.record_priming("B-2026-003", "2.5", "68")
        self.store.record_bottling("B-2026-003", "28", "champagne bottle")
        pk = self.file()["packaging"]
        self.assertTrue(pk["conditioned"])
        self.assertEqual(pk["tax_class"], "sparkling / carbonated")
        self.assertEqual(pk["target_vols"], 2.5)

    def test_a_still_mead_bottles_as_still(self):
        self.store.record_stabilize("B-2026-003", "3.4")
        self.store.record_bottling("B-2026-003", "28", "750 mL bottle")
        self.assertEqual(self.file()["packaging"]["tax_class"], "still")


class SparklingArcTest(SparklingTestCase):
    def act(self):
        return calc.next_action(self.store.load_batch("B-2026-003"),
                                datetime(2026, 9, 6, 10, 0), "Fermaid O")

    def test_the_racked_sentence_offers_both_paths(self):
        t = self.act()["text"]
        self.assertIn("still", t)
        self.assertIn("sparkling", t)

    def test_primed_says_bottle_in_pressure_bottles(self):
        self.store.record_priming("B-2026-003", "2.5", "68")
        a = self.act()
        self.assertIn("Primed to 2.5 volumes", a["text"])
        self.assertIn("pressure-rated bottles", a["text"])


class PrimePageTest(SparklingTestCase):
    def get(self, params=None):
        return dispatch(Request("GET", "/batches/B-2026-003", params or {},
                                {}, ("B-2026-003",), self.store))

    def test_the_carbonate_step_appears_before_stabilizing(self):
        body = self.get().body
        self.assertIn("Carbonate (sparkling)", body)

    def test_the_prime_preview_shows_sugar_and_the_tax_flag(self):
        body = self.get({"prime_vols": "2.5", "prime_temp": "68",
                         "prime_sugar": "honey"}).body
        self.assertIn("g honey", body)
        self.assertIn("pressure-rated bottles only", body)
        self.assertIn("sparkling / carbonated wine for TTB", body)
        self.assertIsNone(self.file().get("primings"))       # preview writes nothing

    def test_a_still_target_says_it_stays_still(self):
        body = self.get({"prime_vols": "1.8", "prime_temp": "68"}).body
        self.assertIn("stays a still wine for excise", body)


if __name__ == "__main__":
    unittest.main()
