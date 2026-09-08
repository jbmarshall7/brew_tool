"""The TTB Report of Wine Premises Operations: the period math, the page,
and the markdown export. Every figure is derived from the batches, so the
tests build batches and check the lines — production, bottled, removals,
losses, and the as-of-period-end inventory that must not drift to 'now'."""
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

GPL = calc.GAL_PER_LITER
BOTTLE = 750 / 1000 * GPL          # a 750 ml bottle in gallons


def august_batch():
    """Bottled in August, some sold, one broken — exercises every line."""
    return {
        "id": "B-2026-001", "recipe": {"name": "Orange Blossom"},
        "pitched_at": "2026-08-05T10:00", "volume_gal": 6.0,
        "measured": {"og": 1.100}, "target": {"fg": 1.000},
        "rackings": [{"at": "2026-08-18T09:00", "volume_gal": 5.9}],
        "packaging": {"at": "2026-08-20T14:00", "units": 28, "unit": "750 ml",
                      "volume_gal": 5.7, "tax_class": "still"},
        "dispositions": [
            {"at": "2026-08-25T12:00", "kind": "sold", "qty": 10, "to": "Cork & Keg"},
            {"at": "2026-08-26T12:00", "kind": "breakage", "qty": 1},
        ],
    }


def bulk_batch():
    """Still in the tank at period end — a bulk-inventory line."""
    return {
        "id": "B-2026-002", "recipe": {"name": "Cyser"},
        "pitched_at": "2026-08-10T10:00", "volume_gal": 6.0,
        "measured": {"og": 1.090}, "target": {"fg": 1.000},
        "rackings": [{"at": "2026-08-28T09:00", "volume_gal": 5.8}],
    }


class TtbMathTest(unittest.TestCase):
    def setUp(self):
        self.batches = [august_batch(), bulk_batch()]
        self.rep = calc.ttb_report(self.batches, "2026-08-01", "2026-08-31")

    def test_production_counts_the_period_pitches(self):
        self.assertEqual(self.rep["production_gal"], 12.0)
        self.assertEqual({p["batch"] for p in self.rep["production"]},
                         {"B-2026-001", "B-2026-002"})

    def test_bottled_is_the_volume_that_went_into_bottles(self):
        self.assertEqual(self.rep["bottled_gal"], 5.7)
        self.assertEqual(len(self.rep["bottled"]), 1)

    def test_removals_bucket_by_tax_class_and_taxable_total(self):
        still = self.rep["removals"]["still"]
        self.assertEqual(still["units"], 10)
        self.assertAlmostEqual(still["gal"], round(10 * BOTTLE, 3))
        # breakage is a loss, not a removal, so it is not a bucket
        self.assertNotIn("breakage", self.rep["removals"])
        self.assertEqual(self.rep["taxable_removals_gal"],
                         round(10 * BOTTLE, 2))

    def test_losses_are_bulk_shortfall_plus_breakage(self):
        # 6.0 made, 5.7 bottled -> 0.3 bulk-to-bottle; plus one broken bottle
        self.assertEqual(self.rep["losses_gal"],
                         round(0.3 + BOTTLE, 2))
        whys = {x["why"] for x in self.rep["losses"]}
        self.assertEqual(whys, {"bulk-to-bottle", "breakage"})

    def test_bottled_inventory_is_as_of_period_end_not_now(self):
        # 28 made, 11 gone (10 sold + 1 broken) by 8/31 -> 17 on hand
        inv = self.rep["bottled_inventory"]
        self.assertEqual(len(inv), 1)
        self.assertEqual(inv[0]["units"], 17)
        self.assertEqual(self.rep["bottled_inventory_gal"],
                         round(17 * BOTTLE, 2))

    def test_bulk_inventory_uses_the_racked_volume(self):
        self.assertEqual(self.rep["bulk_inventory_gal"], 5.8)
        self.assertEqual(self.rep["bulk_inventory"][0]["batch"], "B-2026-002")

    def test_a_later_month_sees_fewer_bottles_on_hand(self):
        # nothing pitched or bottled in September, but the sold/broken bottles
        # are already gone: on-hand carries, production/bottled are zero
        sep = calc.ttb_report(self.batches, "2026-09-01", "2026-09-30")
        self.assertEqual(sep["production_gal"], 0.0)
        self.assertEqual(sep["bottled_gal"], 0.0)
        self.assertEqual(sep["removals"], {})
        self.assertEqual(sep["bottled_inventory"][0]["units"], 17)

    def test_unit_gallons_reads_the_package(self):
        self.assertAlmostEqual(calc.unit_gallons("750 ml"), BOTTLE)
        self.assertAlmostEqual(calc.unit_gallons("1.5 L"), 1.5 * GPL)
        self.assertAlmostEqual(calc.unit_gallons("12 oz"), 12 / 128.0)
        self.assertEqual(calc.unit_gallons("bottle"), None)

    def test_missing_tax_class_is_a_gap_not_a_crash(self):
        b = august_batch()
        b["packaging"]["tax_class"] = None
        rep = calc.ttb_report([b], "2026-08-01", "2026-08-31")
        self.assertTrue(any("tax class" in g for g in rep["gaps"]))

    def test_unpriced_package_flags_a_gap(self):
        b = august_batch()
        b["packaging"]["unit"] = "bottle"       # states no volume
        rep = calc.ttb_report([b], "2026-08-01", "2026-08-31")
        self.assertTrue(any("states no" in g for g in rep["gaps"]))


class TtbPageTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-ttb-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)
        for b in (august_batch(), bulk_batch()):
            self.store.save_batch(b)

    def get(self, path, params=None):
        return dispatch(Request("GET", path, params or {}, {}, (), self.store))

    def post(self, path, form):
        return dispatch(Request("POST", path, {}, form, (), self.store))

    def test_page_renders_the_sections(self):
        r = self.get("/ttb", {"start": "2026-08-01", "end": "2026-08-31"})
        self.assertEqual(r.status, 200)
        for heading in ("Produced by fermentation", "Bottled", "Removals",
                        "Losses", "Period-end inventory"):
            self.assertIn(heading, r.body)
        self.assertIn("B-2026-001", r.body)

    def test_export_writes_a_markdown_file(self):
        r = self.post("/ttb/export", {"start": "2026-08-01",
                                      "end": "2026-08-31"})
        self.assertEqual(r.status, 303)
        report = self.root / "reports" / "ttb-2026-08-01-to-2026-08-31.md"
        self.assertTrue(report.exists())
        text = report.read_text()
        self.assertIn("Produced by fermentation", text)
        self.assertIn("Removals", text)
        # a derived report states it computes no tax
        self.assertIn("no tax", text.lower())


if __name__ == "__main__":
    unittest.main()
