"""The back half of the batch: rack, stabilize, back-sweeten, bottle.

The dose math is pinned by hand-derived values (the sulfite figures match the
old repo's tested constants). The guardrails are the point: sulfite is not
offered on a working ferment, sorbate never goes in without it, and sugar
never goes in before stabilizing — each refusable, each overridable only with
a recorded reason.
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

OWNER = {"gal": "6", "abv": "14", "og": "", "fg": "1.000", "yeast": "71B",
         "demand": "medium", "additions": "4",
         "name": "Orange Blossom Traditional", "honey": "orange blossom"}
RECORD = {"gal": "6", "id": "B-2026-003", "pitched_at": "2026-08-10T15:40",
          "volume_gal": "6", "honey_lb": "18.3", "water_gal": "4.5",
          "yeast_g": "10", "goferm_g": "12.5", "og": "1.1067", "ph": "3.9"}


class DoseMathTest(unittest.TestCase):
    def test_sulfite_matches_the_old_hand_checked_values(self):
        free, _ = calc.molecular_so2_free_needed(3.4)
        self.assertEqual(round(free, 1), 31.9)
        self.assertEqual(calc.kmeta_grams(5, free), 1.049)
        free3, _ = calc.molecular_so2_free_needed(3.0)
        self.assertEqual(round(free3, 1), 13.2)
        self.assertEqual(calc.kmeta_grams(5, free3), 0.433)
        # lower pH genuinely needs less — the reason it is computed
        self.assertLess(calc.kmeta_grams(5, free3), calc.kmeta_grams(5, free))

    def test_sorbate_steps_up_where_it_is_weak(self):
        # base rate at comfortable pH and normal strength
        self.assertEqual(calc.sorbate_grams(6, 3.3, 14),
                         {"g": 3.0, "rate": 0.5, "ppm": 132,
                          "stepped_up": False})
        # high pH → high rate
        self.assertTrue(calc.sorbate_grams(6, 3.6, 14)["stepped_up"])
        # low alcohol → high rate
        self.assertTrue(calc.sorbate_grams(6, 3.3, 8)["stepped_up"])
        self.assertEqual(calc.sorbate_grams(6, 3.6, 14)["g"], 4.5)

    def test_backsweeten_honey(self):
        # 0.998 → 1.010 is 12 pts; 12 * 6 / 35 = 2.057 → 2.06 lb
        self.assertEqual(calc.backsweeten_honey(6, 0.998, 1.010), 2.06)
        with self.assertRaisesRegex(ValueError, "isn't sweeter"):
            calc.backsweeten_honey(6, 1.010, 1.000)


class FinishTestCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-test-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)
        dispatch(Request("POST", "/recipes", {}, OWNER, (), self.store))
        dispatch(Request("POST", "/recipes/orange-blossom-traditional/must",
                         {}, RECORD, (), self.store))

    def flat(self):
        """Two flat readings a few days apart — a stable mead."""
        self.store.add_reading("B-2026-003", "1.000", at="2026-08-28T09:00")
        self.store.add_reading("B-2026-003", "1.000", at="2026-09-02T09:00")

    def file(self):
        return json.loads(
            (self.root / "batches" / "B-2026-003.json").read_text())

    def post(self, path, form):
        return dispatch(Request("POST", path, {}, form, (), self.store))


class RackingTest(FinishTestCase):
    def test_racking_records_the_measured_volume(self):
        b = self.store.record_racking("B-2026-003", "5.7",
                                      at="2026-09-03T09:00", note="off gross lees")
        r = self.file()["rackings"][0]
        self.assertEqual(r["volume_gal"], 5.7)
        self.assertEqual(r["note"], "off gross lees")
        self.assertEqual(calc.current_volume(b), 5.7)

    def test_cannot_rack_into_more_than_you_had(self):
        with self.assertRaisesRegex(ValueError, "more than"):
            self.store.record_racking("B-2026-003", "9")
        self.assertIsNone(self.file().get("rackings"))


class StabilizeTest(FinishTestCase):
    def test_refused_while_still_working(self):
        # one reading, or two that still move: not stable
        self.store.add_reading("B-2026-003", "1.030", at="2026-09-02T09:00")
        with self.assertRaisesRegex(ValueError, "has not held a steady"):
            self.store.record_stabilize("B-2026-003", "3.4")
        self.assertIsNone(self.file().get("stabilizations"))

    def test_stable_mead_gets_both_doses(self):
        self.flat()
        b, d = self.store.record_stabilize("B-2026-003", "3.4",
                                           at="2026-09-03T12:00")
        st = self.file()["stabilizations"][0]
        self.assertEqual(st["kmeta_g"], d["kmeta_g"])
        self.assertEqual(st["sorbate_g"], 3.0)          # 0.5 g/gal × 6
        self.assertEqual(st["ph"], 3.4)
        self.assertEqual(st["volume_gal"], 6.0)
        self.assertTrue(calc.is_stabilized(b))

    def test_dose_follows_the_volume_after_racking(self):
        self.flat()
        self.store.record_racking("B-2026-003", "5.4", at="2026-09-03T09:00")
        b, d = self.store.record_stabilize("B-2026-003", "3.4")
        self.assertEqual(d["gallons"], 5.4)
        self.assertEqual(d["sorbate_g"], 2.7)           # 0.5 × 5.4

    def test_override_lets_a_working_mead_through_with_a_reason(self):
        self.store.add_reading("B-2026-003", "1.030", at="2026-09-02T09:00")
        b, d = self.store.record_stabilize(
            "B-2026-003", "3.4", override_reason="cold-crashed, flat by taste")
        self.assertEqual(self.file()["stabilizations"][0]["override"],
                         "cold-crashed, flat by taste")

    def test_a_second_dose_needs_a_reason(self):
        self.flat()
        self.store.record_stabilize("B-2026-003", "3.4")
        with self.assertRaisesRegex(ValueError, "already stabilized"):
            self.store.record_stabilize("B-2026-003", "3.4")


class SweetenTest(FinishTestCase):
    def test_refused_before_stabilizing(self):
        self.flat()
        with self.assertRaisesRegex(ValueError, "Stabilize first"):
            self.store.record_backsweeten("B-2026-003", "1.012")
        self.assertIsNone(self.file().get("sweetenings"))

    def test_stabilized_then_sweetened(self):
        self.flat()
        self.store.record_stabilize("B-2026-003", "3.4")
        b, honey = self.store.record_backsweeten("B-2026-003", "1.012",
                                                 at="2026-09-04T09:00")
        sw = self.file()["sweetenings"][0]
        self.assertEqual(sw["from_sg"], 1.000)
        self.assertEqual(sw["to_sg"], 1.012)
        self.assertEqual(sw["honey_lb"], honey)
        # the current gravity now reflects the sweetening
        self.assertEqual(calc.current_sg(b), 1.012)

    def test_override_for_a_keg_to_be_force_carbonated(self):
        self.flat()
        b, honey = self.store.record_backsweeten(
            "B-2026-003", "1.012", override_reason="kegging, will force-carb")
        self.assertEqual(self.file()["sweetenings"][0]["override"],
                         "kegging, will force-carb")

    def test_cannot_sweeten_downward(self):
        self.flat()
        self.store.record_stabilize("B-2026-003", "3.4")
        with self.assertRaisesRegex(ValueError, "isn't sweeter"):
            self.store.record_backsweeten("B-2026-003", "0.995")


class BottleTest(FinishTestCase):
    def test_bottling_is_terminal(self):
        self.flat()
        b = self.store.record_bottling("B-2026-003", "28", "750 mL bottle",
                                       at="2026-09-05T10:00")
        pk = self.file()["packaging"]
        self.assertEqual((pk["units"], pk["unit"]), (28, "750 mL bottle"))
        self.assertEqual(pk["volume_gal"], 6.0)
        self.assertTrue(calc.is_bottled(b))
        with self.assertRaisesRegex(ValueError, "already bottled"):
            self.store.record_bottling("B-2026-003", "5", "keg")


class FinishingArcTest(FinishTestCase):
    def act(self, at=datetime(2026, 9, 6, 10, 0)):
        b = self.store.load_batch("B-2026-003")
        return calc.next_action(b, at, "Fermaid O")

    def test_the_sentence_names_each_next_step_in_turn(self):
        self.flat()
        self.assertIn("rack it off the lees", self.act()["text"])
        self.store.record_racking("B-2026-003", "5.7", at="2026-09-03T09:00")
        # the fork: still (stabilize) or sparkling (prime)
        forked = self.act()["text"]
        self.assertIn("stabilize", forked)
        self.assertIn("sparkling", forked)
        self.store.record_stabilize("B-2026-003", "3.4", at="2026-09-03T12:00")
        a = self.act()
        self.assertIn("Back-sweeten to taste", a["text"])
        self.assertIn("bottle it dry", a["text"])
        self.store.record_backsweeten("B-2026-003", "1.012",
                                      at="2026-09-04T09:00")
        self.assertIn("Sweetened to 1.012", self.act()["text"])
        self.store.record_bottling("B-2026-003", "28", "750 mL bottle",
                                   at="2026-09-05T10:00")
        a = self.act()
        self.assertEqual(a["tag"], "Bottled")
        self.assertIn("28 × 750 mL bottle", a["text"])

    def test_racked_but_not_yet_settled_says_wait(self):
        self.store.add_reading("B-2026-003", "1.000", at="2026-09-02T09:00")
        self.store.record_racking("B-2026-003", "5.7", at="2026-09-03T09:00")
        a = self.act()
        self.assertEqual(a["tag"], "Settling")
        self.assertIn("few days flat", a["text"])


class BatchPageTest(FinishTestCase):
    def get(self, params=None):
        return dispatch(Request("GET", "/batches/B-2026-003", params or {},
                                {}, (), self.store))

    def test_the_finishing_card_shows_the_four_steps_when_finished(self):
        self.flat()
        body = self.get().body
        self.assertIn('id="finish"', body)
        for step in ("Rack off the lees", "Stabilize",
                     "Back-sweeten", "Bottle"):
            self.assertIn(step, body)

    def test_stabilize_preview_writes_nothing_and_shows_both_doses(self):
        self.flat()
        body = self.get({"stab_ph": "3.4"}).body
        self.assertIn("potassium metabisulfite", body)
        self.assertIn("3 g potassium sorbate", body)
        self.assertIn("sorbate alone smells of geraniums", body)
        self.assertIn("Record — both go in", body)
        # a preview writes nothing
        self.assertIsNone(self.file().get("stabilizations"))

    def test_sweeten_preview_warns_when_not_stabilized(self):
        self.flat()
        body = self.get({"sweeten_to": "1.012"}).body
        self.assertIn("about 2.06 lb honey", body)   # 12 pts × 6 ÷ 35
        self.assertIn("bottle bombs", body)          # the un-stabilized warning
        self.assertIn("Sweeten without stabilizing", body)  # the override

    def test_a_still_fermenting_batch_keeps_finishing_collapsed(self):
        self.store.add_reading("B-2026-003", "1.040", at="2026-09-02T09:00")
        body = self.get().body
        self.assertNotIn('id="finish"', body)
        self.assertIn("Finishing — rack, stabilize, sweeten, bottle", body)

    def test_the_route_records_and_lands_with_the_next_step(self):
        self.flat()
        r = self.post("/batches/B-2026-003/rack", {"volume_gal": "5.7"})
        self.assertEqual(r.status, 303)
        self.assertIn("Racked", r.location)
        r = self.post("/batches/B-2026-003/stabilize", {"ph": "3.4"})
        self.assertIn("Stabilized", r.location)
        self.assertIn("sorbate", r.location)


if __name__ == "__main__":
    unittest.main()
