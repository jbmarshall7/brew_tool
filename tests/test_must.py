"""Must day: the steps in floor order and the hydrometer check's verdicts."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew.server import Request, dispatch
from brew.store import Store

OWNER = {"gal": "6", "abv": "14", "og": "", "fg": "1.000", "yeast": "71B",
         "demand": "medium", "additions": "4",
         "name": "Orange Blossom Traditional", "honey": "orange blossom"}
MUST = "/recipes/orange-blossom-traditional/must"


class MustTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-test-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)
        dispatch(Request("POST", "/recipes", {}, OWNER, (), self.store))

    def get(self, params=None):
        return dispatch(Request("GET", MUST, params or {}, {}, (), self.store))

    def test_steps_in_floor_order_and_no_banner(self):
        r = self.get({"gal": "6"})
        self.assertEqual(r.status, 200)
        body = r.body
        order = [body.index(t) for t in ("Honey", "Water", "Read it",
                                         "Rehydrate and pitch", "Feed")]
        self.assertEqual(order, sorted(order))
        for expected in ("18.29 lb (18 lb 5 oz)", "start with 4.48 gal (17.0 L)",
                         "top to the 6 gal mark", "250 mL water at 104 °F",
                         "12.5 g Go-Ferm, 10 g 71B",
                         "Fermaid O 26.2 g as 4 × 6.6 g", "Weigh four cups",
                         "SG 1.071", "Nothing after that"):
            self.assertIn(expected, body, expected)
        self.assertNotIn('class="msg', body)
        self.assertIn("<button>Check</button>", body)

    def test_reads_low(self):
        r = self.get({"gal": "6", "reading": "1.101", "temp_f": "76",
                      "cal_f": "60", "ph": "3.9"})
        body = r.body
        self.assertIn('class="msg warn"', body)
        for expected in ("OG 1.1029 (read 1.101 at 76 °F, hydrometer 60 °F)",
                         "3.8 points under 1.1067", "0.87 lb (14 oz) honey",
                         "about 0.07 gal", "13.5 %", "pH 3.9", "happy must"):
            self.assertIn(expected, body, expected)
        self.assertIn("<button>Check again</button>", body)
        self.assertIn('name="reading" type="number" value="1.101"', body)

    def test_reads_high(self):
        r = self.get({"gal": "6", "reading": "1.112", "temp_f": "60"})
        body = r.body
        for expected in ("5.3 points over 1.1067", "0.3 gal (1.1 L) water",
                         "at 6.3 gal", "14.7 %", "past what 71B is rated for"):
            self.assertIn(expected, body, expected)

    def test_on_target(self):
        r = self.get({"gal": "6", "reading": "1.106"})
        self.assertIn('class="msg ok"', r.body)
        self.assertIn("On target", r.body)
        self.assertIn("no sample temperature, so no correction", r.body)

    def test_ph_alone_and_ph_floor(self):
        r = self.get({"gal": "6", "ph": "3.1"})
        self.assertIn('class="msg warn"', r.body)
        self.assertIn("below the 3.2 floor", r.body)

    def test_scaled_to_five(self):
        r = self.get({"gal": "5"})
        self.assertIn("15.24 lb", r.body)
        self.assertIn("5 gal of Orange Blossom Traditional", r.body)

    def test_nonsense_reading_keeps_the_page(self):
        r = self.get({"gal": "6", "reading": "11.01", "ph": "3.9"})
        self.assertEqual(r.status, 200)
        self.assertIn('class="msg err"', r.body)
        self.assertIn("hydrometer reading 11.01 is above 1.25", r.body)
        self.assertIn('<ol class="steps">', r.body)                # the sheet
        self.assertIn('name="reading" type="number" value="11.01"', r.body)
        self.assertIn("<button>Check</button>", r.body)
        self.assertIn("Back to Orange Blossom Traditional", r.body)

    def test_calibration_changes_the_verdict(self):
        r = self.get({"gal": "6", "reading": "1.101", "temp_f": "76",
                      "cal_f": "68"})
        self.assertIn("OG 1.1021 (read 1.101 at 76 °F, hydrometer 68 °F)",
                      r.body)
        self.assertIn("4.6 points under 1.1067", r.body)

    def test_ph_bands(self):
        self.assertIn("low, and it drops further",
                      self.get({"gal": "6", "ph": "3.25"}).body)
        self.assertIn('class="msg warn"', self.get({"gal": "6", "ph": "3.25"}).body)
        self.assertIn("on the low side, fine",
                      self.get({"gal": "6", "ph": "3.6"}).body)
        self.assertIn("unusually high", self.get({"gal": "6", "ph": "7"}).body)

    def test_feed_text_for_five_feedings(self):
        dispatch(Request("POST", "/recipes", {},
                         dict(OWNER, name="Five Feeds", additions="5"), (),
                         self.store))
        body = dispatch(Request("GET", "/recipes/five-feeds/must", {"gal": "6"},
                                {}, (), self.store)).body
        self.assertIn("Weigh five cups now. 24 h, 48 h, 72 h, 96 h, last by "
                      "day 7 or the 1/3 break (SG 1.071)", body)

    def test_links_in(self):
        r = dispatch(Request("GET", "/recipes", {}, {}, (), self.store))
        self.assertIn('href="/recipes/orange-blossom-traditional/must?gal=6"',
                      r.body)
        r = dispatch(Request("GET", "/recipes/orange-blossom-traditional", {},
                             {}, (), self.store))
        self.assertIn('action="/recipes/orange-blossom-traditional/must"',
                      r.body)
        self.assertIn("<button>Make must</button>", r.body)


if __name__ == "__main__":
    unittest.main()
