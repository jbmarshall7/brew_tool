"""Fruit, spice and oak: designing a melomel, and recording what steeped.

The fruit gravity math is the old repo's, hand-checked. The melomel design
takes fruit's sugar off the target so the honey drops to match; the batch
side records additions and watches oak and spice for over-extraction — the
one flavor mistake you cannot pull back.
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


class FruitMathTest(unittest.TestCase):
    def test_sugar_table_and_override(self):
        self.assertEqual(calc.fruit_sugar_pct("blueberry"), 0.10)
        self.assertEqual(calc.fruit_sugar_pct("cherry"), 0.12)
        self.assertEqual(calc.fruit_sugar_pct("other", 8), 0.08)   # percent
        self.assertEqual(calc.fruit_sugar_pct("other", 0.08), 0.08)  # fraction
        with self.assertRaisesRegex(ValueError, "no sugar percentage"):
            calc.fruit_sugar_pct("durian")

    def test_fruit_points(self):
        # 10 lb blueberry (10% sugar) in 6 gal: 10 × .1 × 46 ÷ 6 = 7.67 → 7.7
        self.assertEqual(calc.fruit_points(10, 0.10, 6), 7.7)

    def test_honey_drops_to_match_the_fruit(self):
        # 6 gal to OG 1.1067 = 106.7 pts; fruit gives 7.7, honey supplies 99
        # → 99 × 6 ÷ 35 = 16.97 lb (vs 18.29 with no fruit)
        honey, fpts = calc.honey_for_og_with_fruit(6, 1.1067, 10, 0.10)
        self.assertEqual((honey, fpts), (16.97, 7.7))
        plain, _ = calc.honey_for_og_with_fruit(6, 1.1067)
        self.assertEqual(plain, 18.29)


class MelomelPlanTest(unittest.TestCase):
    def test_the_plan_carries_fruit_and_drops_the_honey(self):
        p = calc.plan(6, 14, fruit="blueberry", fruit_lb=10)
        self.assertEqual(p["honey_lb"], 16.97)
        self.assertEqual(p["fruit"]["item"], "blueberry")
        self.assertEqual(p["fruit"]["points"], 7.7)
        self.assertEqual(p["fruit"]["sugar_pct"], 10.0)
        # fruit brings ~1.11 gal of its own, so the water target drops
        self.assertLess(p["water_gal"], calc.plan(6, 14)["water_gal"])

    def test_a_traditional_still_has_no_fruit(self):
        self.assertIsNone(calc.plan(6, 14)["fruit"])

    def test_too_much_fruit_warns(self):
        p = calc.plan(3, 12, fruit="blackberry", fruit_lb=60)
        self.assertEqual(p["honey_lb"], 0.0)
        self.assertTrue(p["fruit"]["over"])
        self.assertTrue(any("no honey needed" in w for w in p["warnings"]))

    def test_an_unlisted_fruit_needs_a_percentage(self):
        with self.assertRaisesRegex(ValueError, "no sugar percentage"):
            calc.plan(6, 14, fruit="elderberry", fruit_lb=8)
        # ...supplied, it works
        p = calc.plan(6, 14, fruit="elderberry", fruit_lb=8, fruit_pct="9")
        self.assertEqual(p["fruit"]["sugar_pct"], 9.0)


class DesignPageTest(unittest.TestCase):
    def get(self, params):
        return dispatch(Request("GET", "/design", params, {}, (), None))

    def test_the_sheet_shows_a_fruit_row_and_the_adjusted_honey(self):
        body = self.get({"gal": "6", "abv": "14", "fruit": "blueberry",
                         "fruit_lb": "10"}).body
        self.assertIn("10 lb blueberry", body)
        self.assertIn("16.97 lb", body)                # honey, dropped
        self.assertIn("less 7.7 from the blueberry", body)
        self.assertIn("1 lb sugar", body)              # 10 × 10%

    def test_a_traditional_shows_no_fruit_row(self):
        body = self.get({"gal": "6", "abv": "14"}).body
        self.assertIn("18.29 lb", body)
        self.assertNotIn("Fruit</b>", body.replace(" ", ""))


class MelomelRecipeTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-test-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)

    def test_a_melomel_recipe_round_trips(self):
        dispatch(Request("POST", "/recipes", {},
                         {"gal": "6", "abv": "14", "og": "", "fg": "1.000",
                          "yeast": "71B", "demand": "medium", "additions": "4",
                          "fruit": "blueberry", "fruit_lb": "10",
                          "fruit_pct": "", "name": "Blueberry Melomel",
                          "honey": "wildflower"}, (), self.store))
        doc = json.loads((self.root / "recipes" /
                          "blueberry-melomel.json").read_text())
        self.assertEqual(doc["fruit"], {"item": "blueberry", "lb": 10.0,
                                        "sugar_pct": 10.0})
        self.assertEqual(doc["computed"]["honey_lb"], 16.97)
        # reopening it in the designer prefills the fruit
        body = dispatch(Request("GET", "/design",
                                {"recipe": "blueberry-melomel"}, {}, (),
                                self.store)).body
        self.assertIn('name="fruit" type="text" value="blueberry"', body)
        self.assertIn('name="fruit_lb" type="number" value="10.0"', body)


class FlavorTestCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-test-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)
        dispatch(Request("POST", "/recipes", {}, OWNER, (), self.store))
        dispatch(Request("POST", "/recipes/orange-blossom-traditional/must",
                         {}, RECORD, (), self.store))

    def file(self):
        return json.loads(
            (self.root / "batches" / "B-2026-003.json").read_text())

    def test_recording_fruit_spice_oak(self):
        b = self.store.record_flavor("B-2026-003", "fruit", "blueberries",
                                     "10", "lb", at="2026-08-20T09:00")
        fl = self.file()["flavors"][0]
        self.assertEqual((fl["kind"], fl["item"], fl["qty"], fl["unit"]),
                         ("fruit", "blueberries", 10.0, "lb"))
        with self.assertRaisesRegex(ValueError, "isn't one of"):
            self.store.record_flavor("B-2026-003", "sugar", "table")
        with self.assertRaisesRegex(ValueError, "give the fruit"):
            self.store.record_flavor("B-2026-003", "oak", "")

    def test_oak_contact_is_watched_then_stops_when_pulled(self):
        now = datetime(2026, 9, 6, 10, 0)
        # oak goes in during aging, after fermentation — so log it finished
        self.store.add_reading("B-2026-003", "1.000", at="2026-08-18T09:00")
        self.store.record_flavor("B-2026-003", "oak", "medium-toast cubes",
                                 at="2026-08-20T09:00")
        watching = calc.flavors_in_contact(self.store.load_batch("B-2026-003"),
                                           now)
        self.assertEqual(len(watching), 1)
        self.assertEqual(watching[0]["days"], 17)
        # past the watch threshold, the sentence says taste it
        a = calc.next_action(self.store.load_batch("B-2026-003"), now,
                             "Fermaid O")
        self.assertEqual(a["tag"], "Taste the oak")
        self.assertIn("17 days", a["text"])
        # pulling it stops the clock and clears the warning
        self.store.pull_flavor("B-2026-003", 0, at="2026-09-01T09:00")
        self.assertEqual(
            calc.flavors_in_contact(self.store.load_batch("B-2026-003"), now),
            [])

    def test_fruit_is_not_watched_for_over_extraction(self):
        now = datetime(2026, 9, 6, 10, 0)
        self.store.record_flavor("B-2026-003", "fruit", "cherries",
                                 at="2026-07-01T09:00")   # long ago
        self.assertEqual(
            calc.flavors_in_contact(self.store.load_batch("B-2026-003"), now),
            [])

    def test_the_batch_page_shows_the_flavor_section(self):
        self.store.record_flavor("B-2026-003", "oak", "French oak", "2", "oz",
                                 at="2026-08-20T09:00")
        body = dispatch(Request("GET", "/batches/B-2026-003", {}, {},
                                ("B-2026-003",), self.store)).body
        self.assertIn("Fruit, spice &amp; oak", body)
        self.assertIn("French oak", body)
        self.assertIn("Pull it", body)


if __name__ == "__main__":
    unittest.main()
