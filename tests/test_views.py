"""The Design page: the sheet the owner reads, and what happens to bad input."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew import html
from brew.server import Request, dispatch


def get(path, params=None):
    return dispatch(Request("GET", path, params or {}, {}, (), None))


class DesignPageTest(unittest.TestCase):
    def test_first_load_is_already_an_answer(self):
        r = get("/")
        self.assertEqual(r.status, 200)
        self.assertIn("At 6 gal you", r.body)
        self.assertIn("1.091", r.body)             # OG for 12 %
        self.assertIn("15.67 lb", r.body)          # 91.4 * 6 / 35
        self.assertIn('placeholder="6"', r.body)   # 1 g/gal, editable

    def test_the_owners_batch(self):
        r = get("/", {"gal": "6", "abv": "14", "yeast_g": "10"})
        for expected in ("18.29 lb (18 lb 5 oz)", "3.05 lb/gal", "~1.52 gal",
                         "4.48 gal (17.0 L)", "top to the 6 gal mark",
                         "10 g 71B", "(2 sachets)",
                         "12.5 g in 250 mL water at 104 °F",
                         "175 ppm", "26.2 g", "as 4 × 6.6 g", "SG 1.071",
                         "14 % if it finishes at 1.000",
                         "35 pts per lb per gal",
                         "71B is rated about 14 %"):
            self.assertIn(expected, r.body, expected)
        self.assertIn('class="msg warn"', r.body)
        self.assertIn("over 1.100", r.body)     # the pitch-rate hint

    def test_set_by_og_gives_the_same_sheet(self):
        by_abv = get("/", {"gal": "6", "abv": "14", "yeast_g": "10"}).body
        by_og = get("/", {"gal": "6", "abv": "", "og": "1.1067",
                          "yeast_g": "10"}).body
        self.assertIn("strength set by OG", by_og)
        self.assertNotIn("strength set by OG", by_abv)
        for expected in ("18.29 lb", "4.48 gal", "175 ppm", "SG 1.071"):
            self.assertIn(expected, by_og)

    def test_bad_input_keeps_the_form_and_says_why(self):
        r = get("/", {"gal": "abc", "abv": "14"})
        self.assertEqual(r.status, 200)
        self.assertIn('class="msg err"', r.body)
        self.assertIn("isn&#x27;t a number", r.body)
        self.assertIn('name="gal"', r.body)
        self.assertIn('value="abc"', r.body)      # what they typed survives
        self.assertNotIn("you&#x27;ll need", r.body)

    def test_feed_text_follows_the_count(self):
        r = get("/", {"gal": "6", "abv": "14", "additions": "5"})
        self.assertIn("as 5 × 5.2 g", r.body)
        self.assertIn("at 24 h, 48 h, 72 h, 96 h, last by day 7 or the 1/3 "
                      "break (SG 1.071)", r.body)
        r = get("/", {"gal": "6", "abv": "14", "additions": "1"})
        self.assertIn("at 24 h after pitch, or the 1/3 break", r.body)

    def test_touch_targets(self):
        self.assertIn("min-height:44px", html.CSS)
        r = get("/").body
        self.assertIn('inputmode="decimal"', r)
        self.assertIn("<button>Recompute</button>", r)


if __name__ == "__main__":
    unittest.main()
