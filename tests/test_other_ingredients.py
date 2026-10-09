"""Round 15: everything else that goes in is part of the recipe.

The cinnamon and vanilla of a metheglin, a melomel's lime juice and zest,
oak, enzyme, tannin, the honey that back-sweetens — typed one per line under
when it goes in, the way a recipe card is written. A line that starts with
an amount scales with the batch, in the unit a cellar would measure it in
(a 3 BBL batch's lime juice is gallons, not 484 fl oz); one that doesn't is
kept as written. The recipe page lists them by when; the must-day ones join
the must-day steps; a redesign starts from what was saved.
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

LIMEY = """Must day:
1 Tbsp bentonite

Secondary:
26 fl oz key lime juice
tartaric acid, to taste

Tertiary:
3 limes, zest only"""


class ParseTest(unittest.TestCase):
    def test_a_recipe_card_reads_as_it_was_written(self):
        ex = calc.parse_extras(
            "Must day:\n10g Opti-Red\n½ tsp pectic enzyme\n1 1/2 tsp acid blend\n"
            "\nSecondary:\n• 26 fl oz key lime juice\ntartaric acid, to taste\n"
            "1 packet Super-Kleer\n¼ spiral medium-toast American oak\n"
            "71B slurry, if you have it")
        got = [(e["when"], e["qty"], e["unit"], e["what"]) for e in ex]
        self.assertEqual(got, [
            ("Must day", 10.0, "g", "Opti-Red"),
            ("Must day", 0.5, "tsp", "pectic enzyme"),
            ("Must day", 1.5, "tsp", "acid blend"),
            ("Secondary", 26.0, "fl oz", "key lime juice"),
            ("Secondary", None, "", "tartaric acid, to taste"),
            ("Secondary", 1.0, "packet", "Super-Kleer"),
            ("Secondary", 0.25, "spiral", "medium-toast American oak"),
            # a strain name isn't an amount: kept as written
            ("Secondary", None, "", "71B slurry, if you have it"),
        ])

    def test_it_goes_back_into_the_box_unchanged(self):
        ex = calc.parse_extras(LIMEY)
        self.assertEqual(calc.extras_text(ex), LIMEY)
        self.assertEqual(calc.parse_extras(calc.extras_text(ex)), ex)


class ScaleTest(unittest.TestCase):
    def line(self, text, factor):
        return calc.extra_line(calc.parse_extras(text)[0], factor)

    def test_as_written_at_the_recipes_own_size(self):
        self.assertEqual(self.line("¼ spiral medium-toast American oak", 1),
                         "¼ spiral medium-toast American oak")

    def test_scaled_amounts_read_in_cellar_units(self):
        self.assertEqual(self.line("26 fl oz key lime juice", 18.6),
                         "3.78 gal key lime juice")
        self.assertEqual(self.line("1 Tbsp Vietnamese cinnamon", 18.6),
                         "1.16 cups Vietnamese cinnamon")
        self.assertEqual(self.line("1 Tbsp bentonite", 0.2), "0.6 tsp bentonite")
        self.assertEqual(self.line("1.25 lb tupelo honey", 0.5), "10 oz tupelo honey")
        self.assertEqual(self.line("10 g Opti-Red", 18.6), "186 g Opti-Red")
        self.assertEqual(self.line("1 packet Super-Kleer", 18.6),
                         "19 packets Super-Kleer")
        self.assertEqual(self.line("3 limes, zest only", 18.6), "56 limes, zest only")

    def test_a_line_without_an_amount_never_scales(self):
        self.assertEqual(self.line("tartaric acid, to taste", 18.6),
                         "tartaric acid, to taste")
        # a strength isn't an amount
        self.assertEqual(self.line("100 % RO water", 18.6), "100 % RO water")
        self.assertEqual(self.line("30 ppm free SO2 at bottling", 18.6),
                         "30 ppm free SO2 at bottling")


class Case(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-extras-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)
        self.post("/recipes", {"name": "Limey", "gal": "5", "abv": "",
                               "og": "1.106", "fg": "1.007", "yeast": "71B",
                               "demand": "medium", "additions": "4",
                               "extras": LIMEY})
        self.r = self.store.load_recipe("limey")

    def get(self, path, params=None):
        return dispatch(Request("GET", path, params or {}, {}, (), self.store))

    def post(self, path, form):
        return dispatch(Request("POST", path, {}, form, (), self.store))

    @staticmethod
    def card(body):
        return body.split('class="card extras"')[1].split("</div></div>")[0] \
            if 'class="card extras"' in body else ""


class RecipePageTest(Case):
    def test_saved_with_the_recipe_and_the_feed_count_untouched(self):
        self.assertEqual(len(self.r["extras"]), 4)
        self.assertEqual(self.r["additions"], 4)        # Fermaid O feedings

    def test_the_recipe_lists_them_by_when(self):
        card = self.card(self.get("/recipes/limey").body)
        self.assertRegex(card, r"<b>Secondary</b><ul><li><span class=\"amt\">26 fl oz"
                               r"</span> key lime juice</li>")
        self.assertIn("<b>Tertiary</b>", card)
        self.assertIn("limes, zest only", card)

    def test_at_three_barrels_the_lime_juice_is_gallons(self):
        card = self.card(self.get("/recipes/limey", {"gal": "3 bbl"}).body)
        self.assertIn('<span class="amt">3.78 gal</span> key lime juice', card)
        self.assertIn("Scaled from the recipe&#x27;s 5 gal", card)
        self.assertIn("tartaric acid, to taste", card)    # as written


class MustDayTest(Case):
    def test_must_day_ones_join_the_steps_scaled(self):
        body = self.get("/recipes/limey/must", {"gal": "10"}).body
        steps = re.findall(r'<span class="stitle">([^<]+)</span>'
                           r'<span class="big">([^<]+)</span>', body)
        also = dict(steps).get("Also in it")
        self.assertEqual(also, "2 Tbsp bentonite")
        titles = [t for t, _ in steps]
        self.assertLess(titles.index("Also in it"),
                        titles.index("Rehydrate and pitch"))
        self.assertNotIn("lime juice", also)             # that's secondary

    def test_no_list_no_step(self):
        self.post("/recipes", {"name": "Plain", "gal": "5", "abv": "12",
                               "og": "", "fg": "1.000", "yeast": "71B",
                               "demand": "medium", "additions": "4"})
        self.assertNotIn("Also in it", self.get("/recipes/plain/must").body)


class RedesignTest(Case):
    def test_a_redesign_starts_from_what_was_saved_and_keeps_it(self):
        body = self.get("/design", {"recipe": "limey"}).body
        box = re.search(r'<textarea id="f-extras" name="extras">(.*?)</textarea>',
                        body, re.S).group(1)
        self.assertIn("26 fl oz key lime juice", box)
        self.assertIn('class="card extras"', body)        # shown beside the sheet
        r = self.post("/recipes", {"name": "Limey", "gal": "5", "abv": "",
                                   "og": "1.110", "fg": "1.007", "yeast": "71B",
                                   "demand": "medium", "additions": "4",
                                   "extras": box.replace("&#x27;", "'"),
                                   "from_slug": "limey",
                                   "changelog": "a touch more honey"})
        self.assertNotIn("kind=err", r.location)
        r2 = self.store.load_recipe("limey")
        self.assertEqual(r2["version"], 2)
        self.assertEqual(r2["extras"], self.r["extras"])
        self.assertEqual(r2["history"][-1]["extras"], self.r["extras"])


if __name__ == "__main__":
    unittest.main()
