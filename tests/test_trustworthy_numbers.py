"""Round 13: must-day numbers you can trust.

A melomel's fruit scales with the batch, and on must day the hydrometer is
judged against what it can actually see (whole fruit hasn't given up its
sugar yet; juice already has). Water is never negative. A typed fruit sugar
of 1 means 1 %. The volume field belongs to its form. The next-step sentence
doesn't mislead about racked batches, late feeds, or midnight. And one bad
file costs Today one row, not the page.
"""
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew import calc
from brew.server import Request, dispatch
from brew.store import Store
from brew.views_recipes import plan_for


class Case(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-trust-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)

    def get(self, path, params=None):
        return dispatch(Request("GET", path, params or {}, {}, (), self.store))

    def post(self, path, form):
        return dispatch(Request("POST", path, {}, form, (), self.store))

    def recipe(self, name, fruit=None, lb=None, pct="", gal="6", abv="12"):
        f = {"gal": gal, "abv": abv, "og": "", "fg": "1.000", "yeast": "71B",
             "demand": "medium", "additions": "4", "name": name}
        if fruit:
            f.update(fruit=fruit, fruit_lb=str(lb), fruit_pct=pct)
        self.post("/recipes", f)
        return self.store.load_recipe(re.sub(r"[^a-z0-9]+", "-", name.lower()))


class FruitScalesTest(Case):
    def test_half_a_batch_gets_half_the_fruit(self):
        r = self.recipe("Blue", "blueberry", 12)
        full, half = plan_for(r, 6), plan_for(r, 3)
        self.assertEqual(full["fruit"]["lb"], 12.0)
        self.assertEqual(half["fruit"]["lb"], 6.0)
        # same recipe, same per-gallon honey — not half the honey to make
        # room for double the fruit
        self.assertAlmostEqual(half["honey_lb_per_gal"],
                               full["honey_lb_per_gal"], places=2)

    def test_water_is_never_negative(self):
        # a one-gallon cyser on juice: the juice and honey fill the jug
        r = self.recipe("Jug", "apple juice", 8.76, "12", gal="1", abv="12.6")
        p = plan_for(r, 1)
        self.assertEqual(p["water_gal"], 0.0)
        self.assertGreater(p["overfill_gal"], 0)
        self.assertTrue(any("add no water" in w for w in p["warnings"]))
        page = self.get(f"/recipes/{r['slug']}").body
        self.assertNotIn("-0.", re.sub(r"<style.*?</style>", "", page, flags=re.S))

    def test_a_typed_one_percent_is_one_percent(self):
        self.assertAlmostEqual(calc.fruit_sugar_pct("other", "1"), 0.01)
        self.assertAlmostEqual(calc.fruit_sugar_pct("other", "10"), 0.10)
        self.assertAlmostEqual(calc.fruit_sugar_pct("other", "0.08"), 0.08)
        for bad in ("150", "nan", "0.001"):
            with self.assertRaises(ValueError, msg=bad):
                calc.fruit_sugar_pct("other", bad)


class MustDayFruitTest(Case):
    def must(self, r, **params):
        return self.get(f"/recipes/{r['slug']}/must", dict({"gal": "6"}, **params))

    def test_whole_fruit_is_a_step_and_the_check_reads_the_honey_only(self):
        r = self.recipe("Blue", "blueberry", 12)
        p = plan_for(r, 6)
        honey_only = p["og"] - p["fruit"]["points"] / 1000
        body = self.must(r, reading=f"{honey_only:.4f}", temp_f="60").body
        self.assertIn("mesh bag", body)                       # the Fruit step
        self.assertIn("On target", body)                      # honey-only target
        og = re.search(r'id="rec-og"[^>]*value="([^"]+)"', body).group(1)
        # carried forward with the fruit's points added back: the real OG,
        # which the feeds are sized from
        self.assertAlmostEqual(float(og), p["og"], places=3)

    def test_juice_is_counted_by_the_hydrometer_today(self):
        r = self.recipe("Cyser", "apple juice", 24, "12")
        p = plan_for(r, 6)
        body = self.must(r, reading=f"{p['og']:.4f}", temp_f="60").body
        self.assertIn("already dissolved", body)
        self.assertNotIn("mesh bag", body)
        self.assertIn("On target", body)
        og = re.search(r'id="rec-og"[^>]*value="([^"]+)"', body).group(1)
        self.assertAlmostEqual(float(og), p["og"], places=3)  # nothing added

    def test_the_volume_box_is_part_of_the_check(self):
        r = self.recipe("Plain")
        body = self.must(r).body
        box = re.search(r'<input[^>]*name="now_gal"[^>]*>', body).group(0)
        self.assertIn('form="read"', box)
        self.assertIn('id="read"', body)


def batch(**kw):
    b = {"id": "B-2026-001", "pitched_at": "2026-09-01T10:00",
         "measured": {"og": 1.110}, "target": {"fg": 1.000},
         "nutrients": {"stop_sg": 1.073, "product": "fermaid-o",
                       "additions": [{"n": i, "g": 6.6, "stop_sg": 1.073,
                                      "due": f"2026-09-0{1 + i}T10:00"}
                                     for i in (1, 2, 3)]
                       + [{"n": 4, "g": 6.6, "stop_sg": 1.073,
                           "due": "2026-09-08T10:00"}]}}
    b.update(kw)
    return b


class NextActionTest(unittest.TestCase):
    def act(self, b, now):
        return calc.next_action(b, calc.parse_when(now))

    def test_racked_and_flat_above_its_finish_is_stalled_not_ready(self):
        b = batch(readings=[{"at": "2026-09-20T09:00", "sg": 1.041},
                            {"at": "2026-09-23T09:00", "sg": 1.040}],
                  rackings=[{"at": "2026-09-21T09:00", "volume_gal": 5.8}])
        self.assertEqual(self.act(b, "2026-09-23T12:00")["tag"], "Stalled")

    def test_racked_mid_ferment_and_unread_is_not_settling_forever(self):
        b = batch(readings=[{"at": "2026-09-10T09:00", "sg": 1.060},
                            {"at": "2026-09-13T09:00", "sg": 1.040}],
                  rackings=[{"at": "2026-09-14T09:00", "volume_gal": 5.8}])
        self.assertEqual(self.act(b, "2026-09-24T12:00")["tag"],
                         "Reading is old")

    def test_no_feed_nag_after_day_seven(self):
        b = batch(readings=[{"at": "2026-09-10T09:00", "sg": 1.090}])
        a = self.act(b, "2026-09-11T12:00")              # day 10, none logged
        self.assertNotEqual(a["tag"], "Feed due")
        self.assertNotIn("Fermaid", a["text"])

    def test_two_readings_either_side_of_midnight_are_not_a_stall(self):
        # no feeds owed, so nothing outranks the stall rule being tested
        b = batch(pitched_at="2026-09-08T10:00",
                  nutrients={"additions": [], "stop_sg": None},
                  readings=[{"at": "2026-09-09T23:30", "sg": 1.080},
                            {"at": "2026-09-10T00:30", "sg": 1.080}])
        self.assertNotEqual(self.act(b, "2026-09-10T00:45")["tag"], "Stalled")


class TodaySurvivesBadFilesTest(Case):
    def setUp(self):
        super().setUp()
        self.recipe("Plain")
        self.post("/recipes/plain/must",
                  {"gal": "6", "id": "B-2026-001", "pitched_at": "2026-09-01T10:00",
                   "volume_gal": "6", "og": "1.091", "cal_f": "60"})

    def test_a_hand_edited_date_costs_one_row(self):
        b = self.store.load_batch("B-2026-001")
        b["id"] = "B-2026-002"
        b["readings"] = [{"at": "08/03/2026 09:00", "sg": 1.050}]
        self.store.save_batch(b)
        r = self.get("/")
        self.assertEqual(r.status, 200)
        self.assertIn("Can&#x27;t read", r.body)
        self.assertIn("B-2026-002.json", r.body)
        self.assertIn('href="/batches/B-2026-001"', r.body)   # the good one

    def test_a_missing_pitch_date_is_a_row_not_a_500(self):
        b = self.store.load_batch("B-2026-001")
        b["id"] = "B-2026-003"
        del b["pitched_at"]
        self.store.save_batch(b)
        r = self.get("/")
        self.assertEqual(r.status, 200)
        self.assertIn("B-2026-003", r.body)

    def test_an_unparseable_file_is_named(self):
        (self.root / "batches" / "B-2026-009.json").write_text("{ nope")
        r = self.get("/")
        self.assertEqual(r.status, 200)
        self.assertIn("left out", r.body)
        self.assertIn("B-2026-009.json", r.body)


if __name__ == "__main__":
    unittest.main()
