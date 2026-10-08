"""Scale anything to any size, typed the way a cellar says it.

One box takes 6, 6.8 gal, a bucket's 7.9, the conical's 3 bbl, or 350 L —
on the recipe, must day, Design, racking and the vessel list — and the
Recipes page makes every recipe at one typed size. A BBL is a brewer's
barrel, 31 US gallons. At brewhouse size the sheet weighs yeast from a
brick and measures Go-Ferm water in litres.
"""
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew import calc
from brew.server import Request, dispatch
from brew.store import Store

OWNER = {"gal": "6", "abv": "14", "og": "", "fg": "1.000", "yeast": "71B",
         "demand": "medium", "additions": "4", "name": "OB"}


class ParseVolumeTest(unittest.TestCase):
    def test_every_way_a_cellar_says_it(self):
        for typed, gal in [("6", 6), ("6.8 gal", 6.8), ("5 gallons", 5),
                           ("3 bbl", 93), ("3 BBL", 93), ("1 barrel", 31),
                           ("350 L", 92.46), ("20 liters", 5.283),
                           ("6,5", 6.5), (6.8, 6.8)]:
            self.assertAlmostEqual(calc.parse_volume(typed), gal, places=2,
                                   msg=typed)

    def test_nonsense_and_out_of_range_are_refused_in_plain_words(self):
        with self.assertRaisesRegex(ValueError, "try 6, 6.8 gal, 3 bbl"):
            calc.parse_volume("three kegs")
        with self.assertRaisesRegex(ValueError, "below"):
            calc.parse_volume("0")
        with self.assertRaisesRegex(ValueError, "above the 1000 gal"):
            calc.parse_volume("40 bbl")

    def test_brewhouse_sizes_read_in_barrels_too(self):
        self.assertEqual(calc.vol_text(6), "6 gal")
        self.assertEqual(calc.vol_text(93), "93 gal (3 BBL)")
        self.assertEqual(calc.ml_text(124), "124 mL")
        self.assertEqual(calc.ml_text(2376), "2.4 L")


class ScaleCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-scale-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)
        self.post("/recipes", OWNER)

    def get(self, path, params=None):
        return dispatch(Request("GET", path, params or {}, {}, (), self.store))

    def post(self, path, form):
        return dispatch(Request("POST", path, {}, form, (), self.store))


class RecipeAtBrewhouseSizeTest(ScaleCase):
    def test_the_recipe_sheet_at_three_barrels(self):
        body = self.get("/recipes/ob", {"gal": "3 bbl"}).body
        self.assertIn("At 93 gal (3 BBL) you", body)
        self.assertIn('value="3 bbl"', body)              # what they typed stays
        honey_6 = calc.plan(6, 14)["honey_lb"]
        self.assertAlmostEqual(calc.plan("3 bbl", 14)["honey_lb"],
                               honey_6 * 93 / 6, delta=0.05)
        self.assertIn("weigh it from a 500 g brick", body)  # not 37 sachets
        self.assertNotIn("sachets)", body)

    def test_must_day_at_three_barrels(self):
        body = self.get("/recipes/ob/must", {"gal": "3 bbl"}).body
        self.assertIn("93 gal (3 BBL) of OB", body)
        p = calc.plan(93, 14)
        self.assertIn(f"{calc.ml_text(p['goferm_water_ml'])} water", body)
        self.assertGreaterEqual(p["goferm_water_ml"], 1000)  # so it says litres

    def test_design_takes_a_barrel_size(self):
        body = self.get("/design", {"gal": "3 bbl", "abv": "12"}).body
        self.assertIn("At 93 gal (3 BBL) you", body)

    def test_recording_a_conical_batch_stores_gallons(self):
        r = self.post("/recipes/ob/must",
                      {"gal": "3 bbl", "id": "1", "pitched_at": "2026-09-01T10:00",
                       "volume_gal": "3 bbl", "og": "1.107", "cal_f": "60"})
        self.assertNotIn("kind=err", r.location or "", unquote(r.location or ""))
        b = self.store.list_batches()[0]
        self.assertEqual(b["volume_gal"], 93.0)

    def test_a_typo_is_a_banner_not_a_crash(self):
        r = self.get("/recipes/ob", {"gal": "three barrels"})
        self.assertEqual(r.status, 200)
        self.assertIn("something I can read", r.body)


class RecipesListSizeTest(ScaleCase):
    def setUp(self):
        super().setUp()
        self.post("/recipes", dict(OWNER, name="Jug", gal="1", abv="12"))

    def test_one_typed_size_moves_every_make_button(self):
        body = self.get("/recipes", {"size": "3 bbl"}).body
        buttons = re.findall(r'class="btn" href="([^"]+)">Make ([^<]+)<', body)
        self.assertEqual(len(buttons), 2)
        for href, label in buttons:
            self.assertEqual(label, "93 gal (3 BBL)")
            self.assertTrue(href.endswith("gal=93"), href)

    def test_blank_shows_each_at_its_published_size(self):
        body = self.get("/recipes").body
        labels = sorted(re.findall(r'class="btn"[^>]*>Make ([^<]+)<', body))
        self.assertEqual(labels, ["1 gal", "6 gal"])

    def test_a_bad_size_says_so_and_falls_back(self):
        body = self.get("/recipes", {"size": "a lot"}).body
        self.assertIn("something I can read", body)
        self.assertEqual(sorted(re.findall(r'class="btn"[^>]*>Make ([^<]+)<', body)),
                         ["1 gal", "6 gal"])


class VesselsAndRackingTest(ScaleCase):
    def test_the_conical_goes_in_as_three_barrels(self):
        self.post("/vessels/add", {"name": "Conical", "gal": "3 bbl"})
        self.assertEqual(self.store.list_vessels()[0]["gal"], 93.0)
        self.assertIn("93 gal (3 BBL)", self.get("/vessels").body)

    def test_racking_takes_barrels(self):
        self.post("/recipes/ob/must",
                  {"gal": "3 bbl", "id": "1", "pitched_at": "2026-09-01T10:00",
                   "volume_gal": "3 bbl", "og": "1.107", "cal_f": "60"})
        bid = self.store.list_batches()[0]["id"]
        self.store.record_racking(bid, "2.9 bbl", at="2026-09-20T10:00")
        self.assertEqual(calc.current_volume(self.store.load_batch(bid)), 89.9)


if __name__ == "__main__":
    unittest.main()
