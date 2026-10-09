"""Round 15: the recipes, checked against their sources.

Whole fruit on must day: the plan counts the fruit's volume inside the
batch, so the honey sits in the honey and water alone until the fruit goes
in. That's what the hydrometer reads, so that's the target — and it's read
before the fruit hides it. Judging it against the batch OG less the fruit's
points (the old rule) spread the honey over the fruit's room as well, and
told a cherry mead's brewer to add gallons of water. With next to no water
the honey goes straight onto the fruit and there is no target to hold a
reading to. And a recipe's notes — the method, the additions, where it's
from — read as lines, open, with the scale they were written at.
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
        self.root = Path(tempfile.mkdtemp(prefix="brew-audit-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)

    def get(self, path, params=None):
        return dispatch(Request("GET", path, params or {}, {}, (), self.store))

    def post(self, path, form):
        return dispatch(Request("POST", path, {}, form, (), self.store))

    def recipe(self, name, gal, og, fruit=None, lb=None, pct="", notes=""):
        f = {"gal": gal, "abv": "", "og": og, "fg": "1.000", "yeast": "71B",
             "demand": "medium", "additions": "4", "name": name,
             "notes": notes}
        if fruit:
            f.update(fruit=fruit, fruit_lb=str(lb), fruit_pct=pct)
        self.post("/recipes", f)
        return self.store.load_recipe(re.sub(r"[^a-z0-9]+", "-", name.lower()))

    def must(self, r, **params):
        return self.get(f"/recipes/{r['slug']}/must",
                        dict({"gal": calc.num_(r["design_gal"])}, **params)).body

    @staticmethod
    def verdict(body):
        return re.search(r'<div class="msg [a-z]+">(.*?)</div>', body, re.S).group(1)

    @staticmethod
    def rec(body, name):
        return re.search(rf'id="rec-{name}"[^>]*value="([^"]*)"', body).group(1)


class CherryMeadTest(Case):
    """Bucktart, as published: 17 lb buckwheat and 18 lb tart cherries with
    about 3.8 gal of water — 7.2 gal in the fermenter."""

    def setUp(self):
        super().setUp()
        self.r = self.recipe("Bucktart", "7.22", "1.0962", "tart cherries", 18, "12")
        self.p = plan_for(self.r, 7.22)

    def test_the_plan_is_the_published_recipe(self):
        self.assertAlmostEqual(self.p["honey_lb"], 17.0, delta=0.1)
        self.assertAlmostEqual(self.p["water_gal"], 3.8, delta=0.05)

    def test_what_the_honey_and_water_read_is_on_target(self):
        # 17 lb x 35 in 1.42 + 3.8 gal of honey and water
        body = self.must(self.r, reading="1.114", temp_f="60")
        v = self.verdict(body)
        self.assertIn("On target", v)
        self.assertNotIn("water and you", v)             # the old advice
        self.assertAlmostEqual(float(self.rec(body, "og")), self.p["og"], places=3)
        self.assertEqual(self.rec(body, "volume"), "7.22")  # fruit back in

    def test_the_old_rule_would_have_watered_it(self):
        # the old target was OG less the fruit's points over the whole 7.2 gal
        old = self.p["og"] - self.p["fruit"]["points"] / 1000
        self.assertGreater(1.114 - old, 0.030)

    def test_read_comes_before_the_fruit_in_floor_order(self):
        body = self.must(self.r)
        steps = re.findall(r'<span class="stitle">([^<]+)</span>', body)
        self.assertLess(steps.index("Read it"), steps.index("Fruit"))
        self.assertIn("before the fruit and the yeast go in", body)
        box = re.search(r'<input[^>]*name="now_gal"[^>]*>', body).group(0)
        self.assertIn('value="5.22"', box)              # honey and water only

    def test_a_top_up_is_sized_on_the_honey_and_water(self):
        body = self.must(self.r, reading="1.124", temp_f="60")
        v = self.verdict(body)
        liquid = self.p["honey_gal"] + self.p["water_gal"]
        target = self.p["honey_lb"] * 35 / liquid      # ~114: 10 points over
        want = liquid * (124 / target - 1)
        m = re.search(r"Add ([\d.]+) gal", v)
        self.assertAlmostEqual(float(m.group(1)), want, delta=0.02)
        self.assertIn("once the fruit is in", v)

    def test_recording_it_keeps_the_whole_must(self):
        body = self.must(self.r, reading="1.114", temp_f="60")
        r = self.post(f"/recipes/{self.r['slug']}/must",
                      {"gal": "7.22", "id": "1", "pitched_at": "2026-09-01T10:00",
                       "volume_gal": self.rec(body, "volume"),
                       "og": self.rec(body, "og"), "cal_f": "60"})
        self.assertNotIn("kind=err", r.location)
        b = self.store.list_batches()[0]
        self.assertEqual(b["volume_gal"], 7.22)
        self.assertAlmostEqual(b["measured"]["og"], self.p["og"], places=3)


class NoWaterTest(Case):
    """VT HoD, as published: 20 lb honey on 36 lb of thawed fruit, no water."""

    def setUp(self):
        super().setUp()
        self.r = self.recipe("HoD", "5.67", "1.1495",
                             "cherries, raspberries, currants", 36, "8.9")
        self.p = plan_for(self.r, 5.67)

    def test_no_water_and_the_honey_goes_on_the_fruit(self):
        self.assertEqual(self.p["water_gal"], 0.0)
        self.assertAlmostEqual(self.p["honey_lb"], 20.0, delta=0.1)
        body = self.must(self.r)
        self.assertIn("straight onto it", body)
        self.assertIn("before the yeast goes in", body)

    def test_a_reading_has_no_target_and_the_plan_og_is_recorded(self):
        body = self.must(self.r, reading="1.180", temp_f="60")
        v = self.verdict(body)
        self.assertIn("no target", v)
        self.assertNotIn("points over", v)
        self.assertNotIn("points under", v)
        self.assertEqual(self.rec(body, "og"), f"{self.p['og']:.4f}")


class JuiceUnchangedTest(Case):
    def test_juice_still_reads_the_full_og(self):
        r = self.recipe("Cyser", "1.1", "1.095", "apple juice", 8.76, "13")
        p = plan_for(r, 1.1)
        self.assertAlmostEqual(p["honey_lb"], 1.5, delta=0.05)
        body = self.must(r, reading=f"{p['og']:.4f}", temp_f="60")
        self.assertIn("On target", self.verdict(body))
        self.assertIn("already dissolved", body)


class NotesTest(Case):
    NOTES = ("AS PUBLISHED (5 gal): 10 g Opti-Red at pitch.\n"
             "• Back-sweeten with buckwheat honey to balance.")

    def test_notes_are_open_and_keep_their_lines(self):
        r = self.recipe("Plain", "5", "1.100", notes=self.NOTES)
        body = self.get(f"/recipes/{r['slug']}").body
        self.assertRegex(body, r'<details class="sec" open><summary>Notes')
        self.assertIn('class="inner notes"', body)
        self.assertIn(".notes { white-space:pre-line", body)

    def test_scaled_up_the_notes_say_by_how_much(self):
        r = self.recipe("Plain", "5", "1.100", notes=self.NOTES)
        body = self.get(f"/recipes/{r['slug']}", {"gal": "3 bbl"}).body
        self.assertIn("written for 5 gal", body)
        self.assertIn("× 18.6", body)
        self.assertNotIn("× ", self.get(f"/recipes/{r['slug']}").body
                         .split("<summary>Notes")[1].split("</details>")[0])

    def test_must_day_carries_the_notes(self):
        r = self.recipe("Plain", "5", "1.100", notes=self.NOTES)
        body = self.must(r)
        self.assertIn("Opti-Red", body)


if __name__ == "__main__":
    unittest.main()
