"""Recording the must: the batch file, the schedule from the measured OG,
the batch page, and what the next must day already knows."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew.server import Request, dispatch
from brew.store import Store

OWNER = {"gal": "6", "abv": "14", "og": "", "fg": "1.000", "yeast": "71B",
         "yeast_g": "10", "demand": "medium", "additions": "4",
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

    def test_duplicate_id_refused_and_nothing_lost(self):
        self.post(MUST, RECORD)
        before = (self.root / "batches" / "B-2026-003.json").read_text()
        r = self.post(MUST, dict(RECORD, og="1.2000"))
        self.assertEqual(r.status, 303)
        self.assertTrue(r.location.startswith(MUST + "?"))
        self.assertIn("already%20recorded", r.location)
        self.assertIn("og=1.2000", r.location)
        self.assertIn("notes=read+low", r.location)
        self.assertEqual((self.root / "batches" / "B-2026-003.json").read_text(),
                         before)

    def test_bad_id_refused(self):
        r = self.post(MUST, dict(RECORD, id="batch three"))
        self.assertIn("isn%27t%20a%20batch%20id", r.location)
        self.assertEqual(list((self.root / "batches").glob("*.json")), [])

    def test_without_a_check_the_og_is_still_required(self):
        r = self.post(MUST, dict(RECORD, og="", reading="", temp_f=""))
        self.assertEqual(r.status, 200)
        self.assertIn("OG is blank", r.body)

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
        r = self.get(MUST, {"gal": "6"})
        self.assertIn('name="cal_f" type="number" value="68"', r.body)
        self.assertIn("last time B-2026-003 came in at 1.103", r.body)
        self.assertIn('name="id" type="text" value="B-2026-004"', r.body)
        # the recipe page's Make-must form starts from last time's volume
        r = self.get("/recipes/orange-blossom-traditional")
        self.assertIn('name="gal" type="number" value="6.5"', r.body)

    def test_record_form_follows_the_check(self):
        r = self.get(MUST, {"gal": "6", "reading": "1.101", "temp_f": "76",
                            "ph": "3.9"})
        body = r.body
        self.assertIn('<h2 id="record">Pitched? Record it</h2>', body)
        self.assertIn('name="og" type="number" value="1.1029"', body)
        self.assertIn('name="ph" type="number" value="3.9"', body)
        self.assertIn('name="honey_lb" type="number" value="18.29"', body)
        self.assertIn('name="reading" value="1.101"', body)
        self.assertIn("<summary>Check again</summary>", body)
        # without a check the record form is there but tucked away
        body = self.get(MUST, {"gal": "6"}).body
        self.assertIn("Record the must without a check", body)
        self.assertIn('name="og" type="number" value=""', body)


if __name__ == "__main__":
    unittest.main()
