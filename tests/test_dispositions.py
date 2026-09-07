"""Where the bottles went, and how many are left — the foundation the TTB
report and excise worksheets will stand on, and the answer to whether sample
pours add up to a reportable loss.
"""
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
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


class DispositionTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-test-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)
        dispatch(Request("POST", "/recipes", {}, OWNER, (), self.store))
        dispatch(Request("POST", "/recipes/ob/must", {}, RECORD, (),
                         self.store))
        self.store.add_reading("B-2026-003", "1.000", at="2026-08-28T09:00")

    def bottle(self, n=28):
        self.store.record_bottling("B-2026-003", str(n), "750 mL bottle")

    def file(self):
        return json.loads(
            (self.root / "batches" / "B-2026-003.json").read_text())

    def test_cannot_dispose_before_bottling(self):
        with self.assertRaisesRegex(ValueError, "isn't\\s+bottled"):
            self.store.record_disposition("B-2026-003", "sold", "6")

    def test_on_hand_is_bottled_minus_out(self):
        self.bottle(28)
        self.assertEqual(calc.units_on_hand(self.store.load_batch("B-2026-003")),
                         28)
        self.store.record_disposition("B-2026-003", "taproom", "6")
        self.store.record_disposition("B-2026-003", "sold", "10", "Hilltop")
        self.store.record_disposition("B-2026-003", "sample", "2")
        b = self.store.load_batch("B-2026-003")
        self.assertEqual(calc.units_disposed(b), 18)
        self.assertEqual(calc.units_on_hand(b), 10)
        # samples are their own kind, so a loss report can find them
        samples = [d for d in b["dispositions"] if d["kind"] == "sample"]
        self.assertEqual(sum(d["qty"] for d in samples), 2)

    def test_cannot_move_more_than_on_hand(self):
        self.bottle(12)
        self.store.record_disposition("B-2026-003", "sold", "10")
        with self.assertRaisesRegex(ValueError, "only 2 on hand"):
            self.store.record_disposition("B-2026-003", "gift", "5")
        self.assertEqual(len(self.file()["dispositions"]), 1)

    def test_an_unknown_channel_is_refused(self):
        self.bottle()
        with self.assertRaisesRegex(ValueError, "isn't one of"):
            self.store.record_disposition("B-2026-003", "smuggled", "1")

    def test_the_batch_page_shows_bottles_and_on_hand(self):
        self.bottle(28)
        self.store.record_disposition("B-2026-003", "taproom", "6")
        body = dispatch(Request("GET", "/batches/B-2026-003", {}, {},
                                ("B-2026-003",), self.store)).body
        self.assertIn("Bottles — where they went", body)
        self.assertIn(">On hand<", body)
        self.assertIn(">22<", body)              # 28 − 6
        self.assertIn("taproom", body)

    def test_the_bottled_sentence_carries_on_hand(self):
        self.bottle(28)
        self.store.record_disposition("B-2026-003", "sold", "6")
        a = calc.next_action(self.store.load_batch("B-2026-003"),
                             datetime(2026, 9, 6, 10, 0))
        self.assertIn("22 on hand", a["text"])

    def test_the_route_records_and_reports_on_hand(self):
        self.bottle(28)
        r = dispatch(Request("POST", "/batches/B-2026-003/disposition", {},
                             {"kind": "sold", "qty": "6", "to": "Hilltop"}, (),
                             self.store))
        self.assertEqual(r.status, 303)
        self.assertIn("6%20to%20sold", r.location)
        self.assertIn("22%20on%20hand", r.location)


if __name__ == "__main__":
    unittest.main()
