"""Recording the must: the batch file, the schedule from the measured OG,
the batch page, and what the next must day already knows."""
import json
import re
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
RECORD = {"gal": "6", "id": "B-2026-003", "pitched_at": "2026-09-03T15:40",
          "volume_gal": "6", "honey_lb": "18.3", "water_gal": "4.5",
          "yeast_g": "10", "goferm_g": "12.5", "og": "1.1029", "ph": "3.9",
          "reading": "1.101", "temp_f": "76", "cal_f": "60",
          "notes": "read low by 4; stirred, carried on"}
EXPECTED_KEYS = {"added", "id", "measured", "notes", "nutrients",
                 "pitched_at", "recipe", "target", "volume_gal", "yeast"}


class BatchTestCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-test-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)
        dispatch(Request("POST", "/recipes", {}, OWNER, (), self.store))

    def get(self, path, params=None):
        return dispatch(Request("GET", path, params or {}, {}, (), self.store))

    def post(self, path, form):
        return dispatch(Request("POST", path, {}, form, (), self.store))


class StoreIdsTest(BatchTestCase):
    def test_next_id_continues_the_year(self):
        from brew import calc
        self.assertEqual(calc.next_batch_id(self.store.batch_ids(), 2026),
                         "B-2026-001")
        self.post(MUST, RECORD)
        self.assertEqual(calc.next_batch_id(self.store.batch_ids(), 2026),
                         "B-2026-004")


class RecordTest(BatchTestCase):
    def test_writes_the_file_and_lands_on_the_batch(self):
        r = self.post(MUST, RECORD)
        self.assertEqual(r.status, 303)
        self.assertTrue(r.location.startswith("/batches/B-2026-003?msg="))
        for piece in ("Recorded%20B-2026-003", "6%20gal", "OG%201.103",
                      "pH%203.9", "10%20g%2071B%20pitched%20at%203%3A40%20pm",
                      "First%20Fermaid%20O%206.3%20g%20Fri%20Sep%204",
                      "stop%20at%20SG%201.069"):
            self.assertIn(piece, r.location, piece)
        doc = json.loads((self.root / "batches" / "B-2026-003.json").read_text())
        self.assertEqual(set(doc), EXPECTED_KEYS)
        self.assertEqual(doc["recipe"], {"slug": "orange-blossom-traditional",
                                         "name": "Orange Blossom Traditional"})
        self.assertEqual(doc["pitched_at"], "2026-09-03T15:40")
        self.assertEqual(doc["volume_gal"], 6.0)
        self.assertEqual(doc["yeast"], "71B")
        self.assertEqual(doc["target"], {"og": 1.1067, "abv": 14.0, "fg": 1.0})
        self.assertEqual(doc["measured"], {
            "og": 1.1029, "ph": 3.9, "reading": 1.101, "sample_f": 76.0,
            "cal_f": 60.0, "expected_og": 1.1067})
        self.assertEqual(doc["added"], {"honey_lb": 18.3, "water_gal": 4.5,
                                        "yeast_g": 10.0, "goferm_g": 12.5})
        n = doc["nutrients"]
        # sized from the MEASURED 1.1029, not the 1.1067 target
        self.assertEqual(n["from_og"], 1.1029)
        self.assertEqual(n["yan_ppm"], 169)
        self.assertEqual(n["total_g"], 25.3)
        self.assertEqual([a["g"] for a in n["additions"]], [6.3] * 4)
        self.assertEqual([a["due"] for a in n["additions"]],
                         ["2026-09-04T15:40", "2026-09-05T15:40",
                          "2026-09-06T15:40", "2026-09-10T15:40"])
        self.assertTrue(all(a["stop_sg"] == 1.069 for a in n["additions"]))
        self.assertEqual(doc["notes"], "read low by 4; stirred, carried on")

    def bounced(self, r):
        """The must page a refusal lands on, and the query it carried."""
        from urllib.parse import parse_qs, urlparse
        self.assertEqual(r.status, 303)
        u = urlparse(r.location)
        self.assertEqual(u.path, MUST)
        self.assertEqual(u.fragment, "record")        # after the query
        q = {k: v[0] for k, v in parse_qs(u.query, keep_blank_values=True).items()}
        self.assertEqual(q.get("kind"), "err")
        page = self.get(MUST, q)
        self.assertIn('class="msg err"', page.body)
        return q, page.body

    def test_duplicate_id_refused_and_nothing_lost(self):
        self.post(MUST, RECORD)
        before = (self.root / "batches" / "B-2026-003.json").read_text()
        r = self.post(MUST, dict(RECORD, og="1.1100"))
        q, body = self.bounced(r)
        self.assertIn("B-2026-003 is already recorded", q["msg"])
        self.assertIn("B-2026-004", q["msg"])
        self.assertEqual(q["og"], "1.1100")
        self.assertEqual(q["notes"], "read low by 4; stirred, carried on")
        self.assertNotIn("id", q)                      # the next one is offered
        self.assertIn('name="id" type="text" value="B-2026-004"', body)
        self.assertIn('name="og" type="number" value="1.1100"', body)
        self.assertIn("read low by 4; stirred, carried on", body)
        self.assertEqual((self.root / "batches" / "B-2026-003.json").read_text(),
                         before)

    def test_bad_id_refused(self):
        r = self.post(MUST, dict(RECORD, id="batch three"))
        q, body = self.bounced(r)
        self.assertIn("isn't a batch id", q["msg"])
        self.assertEqual(list((self.root / "batches").glob("*.json")), [])

    def test_short_ids_are_filled_out(self):
        for typed, want in (("003", "B-2026-003"), ("7", "B-2026-007"),
                            ("b-2025-3", "B-2025-003")):
            r = self.post(MUST, dict(RECORD, id=typed))
            self.assertEqual(r.location.split("?")[0], f"/batches/{want}",
                             typed)
        # the year comes from the pitch date, not the clock
        r = self.post(MUST, dict(RECORD, id="9", pitched_at="2027-01-05T09:00"))
        self.assertTrue(r.location.startswith("/batches/B-2027-009?"))

    def test_without_a_check_the_og_is_still_required(self):
        r = self.post(MUST, dict(RECORD, og="", reading="", temp_f=""))
        q, body = self.bounced(r)
        self.assertEqual(q["msg"], "OG is blank")
        self.assertEqual(q["notes"], "read low by 4; stirred, carried on")
        self.assertIn("read low by 4; stirred, carried on", body)
        self.assertEqual(list((self.root / "batches").glob("*.json")), [])

    def test_bad_pitch_time_keeps_everything(self):
        r = self.post(MUST, dict(RECORD, pitched_at="9/3/26 3:40"))
        q, body = self.bounced(r)
        self.assertIn("isn't a date and time", q["msg"])
        self.assertIn('value="18.3"', body)
        self.assertEqual(list((self.root / "batches").glob("*.json")), [])

    def test_blank_went_in_fields_mean_none(self):
        self.post(MUST, dict(RECORD, water_gal="", goferm_g=""))
        doc = json.loads((self.root / "batches" / "B-2026-003.json").read_text())
        self.assertEqual(doc["added"]["water_gal"], 0.0)
        self.assertEqual(doc["added"]["goferm_g"], 0.0)
        self.assertEqual(doc["added"]["honey_lb"], 18.3)

    def test_og_at_or_below_fg_refused(self):
        r = self.post(MUST, dict(RECORD, og="0.998"))
        q, _ = self.bounced(r)
        self.assertIn("leave anything to ferment", q["msg"])
        self.assertEqual(list((self.root / "batches").glob("*.json")), [])

    def test_calibration_is_stored(self):
        self.post(MUST, dict(RECORD, cal_f="68"))
        doc = json.loads((self.root / "batches" / "B-2026-003.json").read_text())
        self.assertEqual(doc["measured"]["cal_f"], 68.0)

    def test_volume_after_dilution_sizes_the_feedings(self):
        self.post(MUST, dict(RECORD, volume_gal="6.3", og="1.1067"))
        doc = json.loads((self.root / "batches" / "B-2026-003.json").read_text())
        # 14.0 % -> 175 ppm -> 175/40*6.3 = 27.56 -> 27.6 g
        self.assertEqual(doc["nutrients"]["total_g"], 27.6)


class PagesTest(BatchTestCase):
    def test_batch_page(self):
        self.post(MUST, RECORD)
        r = self.get("/batches/B-2026-003")
        self.assertEqual(r.status, 200)
        body = r.body
        for expected in ("B-2026-003", "Orange Blossom Traditional",
                         "Thu Sep 3, 3:40 pm",
                         "OG 1.103 (read 1.101 at 76 °F, hydrometer 60 °F) "
                         "vs target 1.107",
                         "18.3 lb honey", "10 g 71B", "12.5 g Go-Ferm",
                         "13.5 %", "25.3 g for 169 ppm YAN",
                         "Fri Sep 4, 3:40 pm", "Sat Sep 5, 3:40 pm",
                         "Sun Sep 6, 3:40 pm", "Thu Sep 10, 3:40 pm",
                         "Nothing after this", "read low by 4"):
            self.assertIn(expected, body, expected)
        self.assertEqual(body.count("1.069"), 5)   # four rows + the stop line
        self.assertIn('href="/recipes/orange-blossom-traditional"', body)

    def test_unknown_batch_is_a_banner(self):
        r = self.get("/batches/B-2026-099")
        self.assertEqual(r.status, 200)
        self.assertIn("no batch B-2026-099", r.body)

    def test_recipe_page_lists_the_must(self):
        self.post(MUST, RECORD)
        r = self.get("/recipes/orange-blossom-traditional")
        self.assertIn("Musts recorded", r.body)
        self.assertIn('href="/batches/B-2026-003"', r.body)
        self.assertIn("1.103", r.body)

    def test_next_must_day_already_knows(self):
        self.post(MUST, dict(RECORD, cal_f="68", volume_gal="6.5"))
        # the id's year comes from the pitch date the form carries, so this
        # holds on any day the suite runs
        r = self.get(MUST, {"gal": "6", "pitched_at": "2026-09-10T09:00"})
        self.assertIn('name="cal_f" type="number" value="68"', r.body)
        self.assertIn("last time B-2026-003 came in at 1.103", r.body)
        self.assertIn('name="id" type="text" value="B-2026-004"', r.body)
        r = self.get(MUST, {"gal": "6", "pitched_at": "2027-01-05T09:00"})
        self.assertIn('name="id" type="text" value="B-2027-001"', r.body)
        # the recipe page's Make-must form starts from last time's volume
        r = self.get("/recipes/orange-blossom-traditional")
        self.assertIn('name="gal" type="number" value="6.5"', r.body)

    def test_record_form_follows_the_check(self):
        r = self.get(MUST, {"gal": "6", "reading": "1.101", "temp_f": "76",
                            "ph": "3.9"})
        body = r.body
        self.assertIn('<h2 id="record" class="noprint">Pitched? Record it</h2>',
                      body)
        self.assertIn('name="og" type="number" value="1.1029"', body)
        self.assertIn('id="rec-ph" name="ph" type="number" value="3.9"', body)
        self.assertIn('name="honey_lb" type="number" value="18.29"', body)
        self.assertIn('name="reading" value="1.101"', body)
        # a low reading asks for a re-read, so the check form stays open
        self.assertIn('<details class="sec" open><summary>Check again</summary>',
                      body)
        # ...and on target it tucks away
        body = self.get(MUST, {"gal": "6", "reading": "1.106"}).body
        self.assertIn('<details class="sec"><summary>Check again</summary>',
                      body)
        # every id on the page is unique, so labels focus the right field
        ids = re.findall(r' id="([^"]+)"', body)
        self.assertEqual(len(ids), len(set(ids)), sorted(
            i for i in ids if ids.count(i) > 1))
        # without a check the record form is there but tucked away
        body = self.get(MUST, {"gal": "6"}).body
        self.assertIn("Record the must without a check", body)
        self.assertIn('name="og" type="number" value=""', body)

    def test_feed_step_follows_the_measured_og(self):
        # target-sized before a check...
        body = self.get(MUST, {"gal": "6"}).body
        self.assertIn("Fermaid O 26.2 g as 4 × 6.6 g", body)
        self.assertIn("SG 1.071", body)
        # ...sized from the measured OG after one, matching the file
        body = self.get(MUST, {"gal": "6", "reading": "1.101",
                               "temp_f": "76"}).body
        self.assertIn("Fermaid O 25.3 g as 4 × 6.3 g", body)
        self.assertIn("Sized from your OG 1.103 at 6 gal", body)
        self.assertIn("(SG 1.069)", body)
        self.assertNotIn("6.6 g", body)

    def test_volume_now_feeds_the_correction_and_the_record(self):
        body = self.get(MUST, {"gal": "6", "reading": "1.112",
                               "temp_f": "60"}).body
        self.assertIn("put 6.3 in &#x27;volume now&#x27;", body)
        self.assertIn('name="now_gal" type="number" value="6"', body)
        # after the top-up the owner says what's in the carboy now
        body = self.get(MUST, {"gal": "6", "now_gal": "6.3", "reading": "1.107",
                               "temp_f": "60"}).body
        self.assertIn("On target", body)
        self.assertIn('name="volume_gal" type="number" value="6.3"', body)
        self.assertIn("at 6.3 gal", body)              # the feed step's sizing


if __name__ == "__main__":
    unittest.main()
