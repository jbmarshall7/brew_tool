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
         "demand": "medium", "additions": "4",
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
        self.assertNotIn("yeast_g", doc)          # derived, not stored
        self.assertEqual(doc["design_gal"], 6.0)
        self.assertEqual(doc["strength"], {"by": "abv", "abv": 14.0,
                                           "og": None, "fg": 1.0})
        # honey weight lives only inside computed: the inputs are the recipe
        top = {k for k in doc if k != "computed"}
        self.assertNotIn("honey_lb", top)
        self.assertNotIn("og", top)
        c = doc["computed"]
        self.assertEqual(c["yeast_g"], 10.0)
        self.assertEqual(c["honey_lb"], 18.29)
        self.assertEqual(c["og"], 1.1067)
        self.assertEqual(c["water_gal"], 4.48)
        self.assertEqual(c["yan_ppm"], 175)
        # ...and it is exactly what a fresh plan() from the inputs says
        p = calc.plan(6, 14)
        for k, v in c.items():
            self.assertEqual(v, p[k], k)
        # written stably: sorted keys, indented, trailing newline
        text = path.read_text()
        self.assertTrue(text.endswith("}\n"))
        self.assertEqual(json.dumps(doc, indent=2, sort_keys=True,
                                    ensure_ascii=False) + "\n", text)

    def test_blank_name_refused_and_nothing_lost(self):
        from urllib.parse import parse_qs, urlparse
        r = self.post("/recipes", dict(OWNER, name="  ", abv="13.5",
                                       notes="try D47 next time"))
        self.assertEqual(r.status, 303)
        u = urlparse(r.location)
        self.assertEqual(u.path, "/")
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        self.assertIn("Give the recipe a name", q["msg"])
        self.assertEqual(q["abv"], "13.5")
        self.assertEqual(q["notes"], "try D47 next time")
        body = self.get("/", q).body
        self.assertIn('class="msg err"', body)
        self.assertIn('name="abv" type="number" value="13.5"', body)
        self.assertIn("try D47 next time", body)
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
        self.assertIn("10 g 71B", r.body)         # 5 gal over 1.100: 2 sachets
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
        self.assertIn('name="yeast" type="text" value="71B"', r.body)
        self.assertIn('name="from_slug" value="orange-blossom-traditional"',
                      r.body)
        self.assertIn("Save changes to Orange Blossom Traditional", r.body)
        self.assertIn('value="orange blossom"', r.body)

    def test_design_page_is_one_form_so_a_recompute_keeps_the_name(self):
        r = self.get("/", {"gal": "6", "abv": "14",
                           "name": "Orange Blossom Traditional",
                           "honey": "orange blossom", "notes": "keep"})
        body = r.body
        self.assertEqual(body.count("<form"), 1)
        self.assertIn('<button formmethod="post" formaction="/recipes">'
                      "Save recipe</button>", body)
        self.assertIn('name="name" type="text" value="Orange Blossom '
                      'Traditional"', body)
        self.assertIn('value="orange blossom"', body)
        self.assertIn(">keep</textarea>", body)
        # the save card sits inside the targets form, after the sheet
        self.assertLess(body.index('id="targets"'), body.index('class="card save"'))
        self.assertLess(body.index('class="card save"'), body.index("</form>"))

    def test_cleared_abv_means_set_by_og(self):
        r = self.get("/", {"gal": "6", "abv": "", "og": "1.1067"})
        self.assertIn('name="abv" type="number" value=""', r.body)
        self.assertIn("Strength is set by the OG below", r.body)
        self.assertIn("18.29 lb", r.body)

    def test_typed_strings_are_escaped_everywhere(self):
        self.post("/recipes", dict(OWNER, name='Cyser "2" <b>',
                                   honey="<i>oak</i>",
                                   notes="<script>x</script>"))
        lst = self.get("/recipes").body
        main = lst.split("<main>")[1]
        self.assertIn("Cyser &quot;2&quot; &lt;b&gt;", main)
        self.assertNotIn('"2" <b>', main)
        self.assertNotIn("<i>oak", main)
        red = self.get("/", {"recipe": "cyser-2-b"}).body
        for expected in ('value="Cyser &quot;2&quot; &lt;b&gt;"',
                         'value="&lt;i&gt;oak&lt;/i&gt;"',
                         "&lt;script&gt;x&lt;/script&gt;"):
            self.assertIn(expected, red)
        self.assertNotIn("<script>x", red)
        must = self.get("/recipes/cyser-2-b/must").body
        self.assertNotIn('"2" <b>', must)
        self.assertIn("Cyser &quot;2&quot; &lt;b&gt;", must)

    def test_pages_never_read_the_cached_computed_block(self):
        self.post("/recipes", OWNER)
        path = self.root / "recipes" / "orange-blossom-traditional.json"
        doc = json.loads(path.read_text())
        doc["strength"]["abv"] = 13.0           # a hand edit, computed stale
        del doc["computed"]
        path.write_text(json.dumps(doc))
        self.assertIn("13 % · OG 1.099", self.get("/recipes").body)
        page = self.get("/recipes/orange-blossom-traditional").body
        self.assertIn("2.83 lb per gallon", page)
        self.assertIn("16.97 lb", page)

    def test_one_broken_file_costs_one_row(self):
        self.post("/recipes", OWNER)
        (self.root / "recipes" / "wildflower.json").write_text(
            '{"name": "Wildflower",}')
        home = self.get("/").body
        self.assertIn('id="targets"', home)
        lst = self.get("/recipes").body
        self.assertIn("Orange Blossom Traditional", lst)
        self.assertIn('class="msg warn"', lst)
        self.assertIn("wildflower.json isn&#x27;t valid JSON", lst)

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
