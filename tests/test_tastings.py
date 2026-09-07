"""Tasting notes and recipe versioning — the two memory aids, most valuable
before the cellar fills to eight batches nobody can hold in their head."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew import calc
from brew.server import Request, dispatch
from brew.store import Store

OWNER = {"gal": "6", "abv": "14", "og": "", "fg": "1.000", "yeast": "71B",
         "demand": "medium", "additions": "4", "name": "OB", "honey": "orange"}
RECORD = {"gal": "6", "id": "B-2026-003", "pitched_at": "2026-08-10T15:40",
          "volume_gal": "6", "honey_lb": "18.3", "water_gal": "4.5",
          "yeast_g": "10", "goferm_g": "12.5", "og": "1.1067", "ph": "3.9"}


class TastingTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-test-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)
        dispatch(Request("POST", "/recipes", {}, OWNER, (), self.store))
        dispatch(Request("POST", "/recipes/ob/must", {}, RECORD, (),
                         self.store))

    def file(self):
        return json.loads(
            (self.root / "batches" / "B-2026-003.json").read_text())

    def test_a_tasting_takes_a_stage_and_a_score_or_note(self):
        b = self.store.record_tasting("B-2026-003", "post-primary", "4",
                                      "clean, a little hot", at="2026-08-25T09:00")
        t = self.file()["tastings"][0]
        self.assertEqual((t["stage"], t["overall"]), ("post-primary", 4))
        self.assertEqual(t["note"], "clean, a little hot")

    def test_an_unknown_stage_is_refused(self):
        with self.assertRaisesRegex(ValueError, "isn't one of"):
            self.store.record_tasting("B-2026-003", "midnight snack", "3")

    def test_a_tasting_needs_a_score_or_a_note(self):
        with self.assertRaisesRegex(ValueError, "score or a note"):
            self.store.record_tasting("B-2026-003", "at bottling")

    def test_the_batch_page_shows_the_tasting_section(self):
        self.store.record_tasting("B-2026-003", "post-primary", "4", "clean",
                                  at="2026-08-25T09:00")
        body = dispatch(Request("GET", "/batches/B-2026-003", {}, {},
                                ("B-2026-003",), self.store)).body
        self.assertIn("Tastings", body)
        self.assertIn("post-primary", body)
        self.assertIn("★★★★☆", body)
        self.assertIn("clean", body)

    def test_the_route_records(self):
        r = dispatch(Request("POST", "/batches/B-2026-003/tasting", {},
                             {"stage": "post-primary", "overall": "5",
                              "note": "lovely"}, (), self.store))
        self.assertEqual(r.status, 303)
        self.assertIn("Tasting%20noted", r.location)
        self.assertEqual(len(self.file()["tastings"]), 1)


class VersioningTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-test-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)

    def post(self, form):
        return dispatch(Request("POST", "/recipes", {}, form, (), self.store))

    def get(self, path, params=None):
        return dispatch(Request("GET", path, params or {}, {}, (), self.store))

    def test_the_recipe_page_shows_the_version_history(self):
        self.post(OWNER)
        self.post(dict(OWNER, abv="13", changelog="dropped to 13 %",
                       from_slug="ob"))
        body = self.get("/recipes/ob").body
        self.assertIn("Versions (now v2)", body)
        self.assertIn("dropped to 13 %", body)
        self.assertIn("initial version", body)

    def test_a_batch_pins_the_version_it_was_made_from(self):
        self.post(OWNER)                      # v1
        dispatch(Request("POST", "/recipes/ob/must", {}, RECORD, (),
                         self.store))         # batch off v1
        self.post(dict(OWNER, abv="13", changelog="dropped", from_slug="ob"))
        doc = json.loads(
            (self.root / "batches" / "B-2026-003.json").read_text())
        self.assertEqual(doc["recipe"]["version"], 1)     # still points at v1

    def test_the_redesign_form_asks_what_changed(self):
        self.post(OWNER)
        body = self.get("/design", {"recipe": "ob"}).body
        self.assertIn("What changed?", body)


if __name__ == "__main__":
    unittest.main()
