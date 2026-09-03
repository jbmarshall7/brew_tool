"""Saving a design as a recipe, listing, scaling, redesigning."""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew import calc
from brew.server import Request, dispatch
from brew.store import Store, slugify
from brew.views_design import SCRIPT

OWNER = {"gal": "6", "abv": "14", "og": "", "fg": "1.000", "yeast": "71B",
         "yeast_g": "10", "demand": "medium", "additions": "4",
         "name": "Orange Blossom Traditional", "honey": "orange blossom",
         "notes": ""}


class RecipeTestCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-test-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)

    def get(self, path, params=None):
        return dispatch(Request("GET", path, params or {}, {}, (), self.store))

    def post(self, path, form):
        return dispatch(Request("POST", path, {}, form, (), self.store))


class SlugTest(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("Orange Blossom Traditional"),
                         "orange-blossom-traditional")
        self.assertEqual(slugify("  Cyser #2 (dry) "), "cyser-2-dry")
        self.assertEqual(slugify("!!!"), "recipe")


class SaveTest(RecipeTestCase):
    def test_save_lands_on_the_recipe_with_a_banner(self):
        r = self.post("/recipes", OWNER)
        self.assertEqual(r.status, 303)
        self.assertTrue(r.location.startswith(
            "/recipes/orange-blossom-traditional?msg="))
        self.assertIn("Saved%20Orange%20Blossom%20Traditional", r.location)
        self.assertIn("3.05%20lb%20orange%20blossom%20per%20gallon", r.location)
        self.assertIn("18.29%20lb%20for%206%20gal", r.location)

    def test_the_file(self):
        self.post("/recipes", OWNER)
        path = self.root / "recipes" / "orange-blossom-traditional.json"
        doc = json.loads(path.read_text())
        self.assertEqual(doc["name"], "Orange Blossom Traditional")
        self.assertEqual(doc["honey"], "orange blossom")
        self.assertEqual(doc["yeast"], "71B")
        self.assertEqual(doc["yeast_g"], 10.0)
        self.assertEqual(doc["design_gal"], 6.0)
        self.assertEqual(doc["strength"], {"by": "abv", "abv": 14.0,
                                           "og": None, "fg": 1.0})
        # honey weight lives only inside computed: the inputs are the recipe
        top = {k for k in doc if k != "computed"}
        self.assertNotIn("honey_lb", top)
        self.assertNotIn("og", top)
        c = doc["computed"]
        self.assertEqual(c["honey_lb"], 18.29)
        self.assertEqual(c["og"], 1.1067)
        self.assertEqual(c["water_gal"], 4.48)
        self.assertEqual(c["yan_ppm"], 175)
        # ...and it is exactly what a fresh plan() from the inputs says
        p = calc.plan(6, 14, yeast_g=10)
        for k, v in c.items():
            self.assertEqual(v, p[k], k)
        # written stably: sorted keys, indented, trailing newline
        text = path.read_text()
        self.assertTrue(text.endswith("}\n"))
        self.assertEqual(json.dumps(doc, indent=2, sort_keys=True,
                                    ensure_ascii=False) + "\n", text)

    def test_blank_name_refused(self):
        r = self.post("/recipes", dict(OWNER, name="  "))
        self.assertEqual(r.status, 200)
        self.assertIn("Give the recipe a name", r.body)
        self.assertEqual(list((self.root / "recipes").glob("*.json")), [])

    def test_duplicate_name_refused_and_nothing_lost(self):
        self.post("/recipes", OWNER)
        r = self.post("/recipes", dict(OWNER, abv="13"))
        self.assertEqual(r.status, 303)
        self.assertTrue(r.location.startswith("/?"))
        self.assertIn("abv=13", r.location)
        self.assertIn("name=Orange+Blossom+Traditional", r.location)
        self.assertIn("already%20a%20recipe%20called", r.location)
        doc = json.loads((self.root / "recipes" /
                          "orange-blossom-traditional.json").read_text())
        self.assertEqual(doc["strength"]["abv"], 14.0)   # untouched

    def test_redesign_overwrites_in_place(self):
        self.post("/recipes", OWNER)
        r = self.post("/recipes", dict(OWNER, abv="13", name="OB Trad 13",
                                       from_slug="orange-blossom-traditional"))
        self.assertTrue(r.location.startswith(
            "/recipes/orange-blossom-traditional?msg=Updated"))
        doc = json.loads((self.root / "recipes" /
                          "orange-blossom-traditional.json").read_text())
        self.assertEqual(doc["strength"]["abv"], 13.0)
        self.assertEqual(doc["name"], "OB Trad 13")
        self.assertEqual(len(list((self.root / "recipes").glob("*.json"))), 1)


class PagesTest(RecipeTestCase):
    def test_empty_list_points_at_design(self):
        r = self.get("/recipes")
        self.assertIn("No recipes yet", r.body)
        self.assertIn('href="/"', r.body)

    def test_list_and_page(self):
        self.post("/recipes", OWNER)
        r = self.get("/recipes")
        self.assertIn("Orange Blossom Traditional", r.body)
        self.assertIn("14 % · OG 1.107", r.body)
        r = self.get("/recipes/orange-blossom-traditional")
        self.assertEqual(r.status, 200)
        self.assertIn("18.29 lb", r.body)
        self.assertIn("10 g 71B", r.body)
        self.assertIn('href="/?recipe=orange-blossom-traditional"', r.body)

    def test_scaled_to_five_gallons(self):
        self.post("/recipes", OWNER)
        r = self.get("/recipes/orange-blossom-traditional", {"gal": "5"})
        self.assertIn("15.24 lb", r.body)
        self.assertIn("8.3 g 71B", r.body)        # 10 g at 6 gal, scaled
        self.assertIn("At 5 gal you", r.body)

    def test_unknown_recipe_is_a_banner(self):
        r = self.get("/recipes/nope")
        self.assertEqual(r.status, 200)
        self.assertIn("no recipe called", r.body)

    def test_redesign_prefills_the_design_page(self):
        self.post("/recipes", OWNER)
        r = self.get("/", {"recipe": "orange-blossom-traditional"})
        self.assertIn("Redesign Orange Blossom Traditional", r.body)
        self.assertIn('name="abv" type="number" value="14"', r.body)
        self.assertIn('name="yeast_g" type="number" value="10"', r.body)
        self.assertIn('name="from_slug" value="orange-blossom-traditional"',
                      r.body)
        self.assertIn("Save changes to Orange Blossom Traditional", r.body)
        self.assertIn('value="orange blossom"', r.body)

    def test_design_page_offers_save_and_carries_inputs(self):
        r = self.get("/", {"gal": "6", "abv": "14", "yeast_g": "10"})
        self.assertIn('action="/recipes"', r.body)
        self.assertIn('name="gal" value="6"', r.body)
        self.assertIn('name="yeast_g" value="10"', r.body)
        self.assertIn("<button>Save recipe</button>", r.body)

    def test_the_script_is_only_a_submit(self):
        self.assertIn("f.submit()", SCRIPT)
        for forbidden in ("fetch", "import", "src=", "localStorage",
                          "XMLHttpRequest", "eval"):
            self.assertNotIn(forbidden, SCRIPT, forbidden)
        self.assertIsNone(re.search(r"\d\s*[-+*/]\s*\d", SCRIPT),
                          "no arithmetic in the browser")
        r = self.get("/")
        self.assertIn(SCRIPT, r.body)
        self.assertNotIn("<script", self.get("/recipes").body)


if __name__ == "__main__":
    unittest.main()
