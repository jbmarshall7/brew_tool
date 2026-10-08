"""The TTB Report of Wine Premises Operations: the period math, its two
balances, the tax classes, the page, and the markdown export.

Every figure is derived from the batches, so the tests build batches and
check the lines. The invariant that matters most: each period balances —
on hand at start + in − out − losses = on hand at end, for bulk and for
bottled — and one period's end is the next one's start. The first version
of this report failed that (a racking loss booked at the bottling, and
"bottled" counted as the bulk gallons, not what the bottles held).
"""
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew import calc
from brew.server import Request, dispatch
from brew.store import Store

GPL = calc.GAL_PER_LITER
BOTTLE = 750 / 1000 * GPL          # a 750 ml bottle in gallons
MONTHS = [("2026-07-01", "2026-07-31"), ("2026-08-01", "2026-08-31"),
          ("2026-09-01", "2026-09-30"), ("2026-10-01", "2026-10-31")]


def august_batch():
    """Bottled in August, some sold, one broken — exercises every line."""
    return {
        "id": "B-2026-001", "recipe": {"name": "Orange Blossom"},
        "pitched_at": "2026-08-05T10:00", "volume_gal": 6.0,
        "measured": {"og": 1.100}, "target": {"fg": 1.000},
        "readings": [{"at": "2026-08-14T09:00", "sg": 1.002},
                     {"at": "2026-08-16T09:00", "sg": 1.000}],
        "rackings": [{"at": "2026-08-18T09:00", "volume_gal": 5.9}],
        "packaging": {"at": "2026-08-20T14:00", "units": 28, "unit": "750 ml",
                      "volume_gal": 5.9, "tax_class": "still ≤16 %"},
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


def assert_books(test, batches):
    """Every month balances, and each month's end is the next one's start."""
    prev = None
    for s, e in MONTHS:
        r = calc.ttb_report(batches, s, e)
        b = r["balance"]
        test.assertTrue(b["ok"], f"{s}: {b}")
        test.assertAlmostEqual(b["bulk"]["residual"], 0, places=3)
        test.assertAlmostEqual(b["bottled"]["residual"], 0, places=3)
        if prev is not None:
            test.assertAlmostEqual(b["bulk"]["begin"], prev[0], places=2, msg=s)
            test.assertAlmostEqual(b["bottled"]["begin"], prev[1], places=2,
                                   msg=s)
        prev = (b["bulk"]["end"], b["bottled"]["end"])


class TtbMathTest(unittest.TestCase):
    def setUp(self):
        self.batches = [august_batch(), bulk_batch()]
        self.rep = calc.ttb_report(self.batches, "2026-08-01", "2026-08-31")

    def test_production_counts_the_period_pitches(self):
        self.assertEqual(self.rep["production_gal"], 12.0)
        self.assertEqual({p["batch"] for p in self.rep["production"]},
                         {"B-2026-001", "B-2026-002"})

    def test_bottled_is_what_the_bottles_hold_not_the_bulk(self):
        # 28 x 750 ml is 5.55 gal; 5.9 gal was drawn from the tank
        self.assertEqual(self.rep["bottled_gal"], round(28 * BOTTLE, 2))
        row = self.rep["bottled"][0]
        self.assertEqual(row["drawn_gal"], 5.9)
        self.assertEqual(row["tax_class"], "still ≤16 %")

    def test_removals_bucket_by_tax_class_and_taxable_total(self):
        still = self.rep["removals"]["still ≤16 %"]
        self.assertEqual(still["units"], 10)
        self.assertAlmostEqual(still["gal"], round(10 * BOTTLE, 3))
        # breakage is a loss, not a removal, so it is not a bucket
        self.assertNotIn("breakage", self.rep["removals"])
        self.assertEqual(self.rep["taxable_removals_gal"],
                         round(10 * BOTTLE, 2))
        self.assertEqual(self.rep["taxable_by_class"],
                         {"still ≤16 %": round(10 * BOTTLE, 2)})

    def test_each_loss_is_booked_on_its_own_day(self):
        got = {(x["batch"], x["why"], x["date"]): x["gal"]
               for x in self.rep["losses"]}
        self.assertEqual(got[("B-2026-001", "racking", "2026-08-18")], 0.1)
        self.assertEqual(got[("B-2026-002", "racking", "2026-08-28")], 0.2)
        self.assertAlmostEqual(got[("B-2026-001", "bottling", "2026-08-20")],
                               5.9 - 28 * BOTTLE, places=3)
        self.assertAlmostEqual(got[("B-2026-001", "breakage", "2026-08-26")],
                               BOTTLE, places=3)
        self.assertEqual(self.rep["losses_gal"],
                         round(0.1 + 0.2 + (5.9 - 28 * BOTTLE) + BOTTLE, 2))

    def test_the_period_balances(self):
        b = self.rep["balance"]
        self.assertTrue(b["ok"])
        self.assertEqual(b["bulk"]["begin"], 0.0)
        self.assertEqual(b["bulk"]["end"], 5.8)
        self.assertEqual(self.rep["gaps"], [])

    def test_bottled_inventory_is_as_of_period_end_not_now(self):
        # 28 made, 11 gone (10 sold + 1 broken) by 8/31 -> 17 on hand
        inv = self.rep["bottled_inventory"]
        self.assertEqual(len(inv), 1)
        self.assertEqual(inv[0]["units"], 17)
        self.assertEqual(self.rep["bottled_inventory_gal"],
                         round(17 * BOTTLE, 2))

    def test_bulk_inventory_uses_the_racked_volume_and_the_stage_then(self):
        self.assertEqual(self.rep["bulk_inventory_gal"], 5.8)
        row = self.rep["bulk_inventory"][0]
        self.assertEqual((row["batch"], row["tag"]), ("B-2026-002", "racked"))
        # in July neither existed; in mid-August the cyser was still working
        mid = calc.ttb_report(self.batches, "2026-08-01", "2026-08-20")
        self.assertEqual(mid["bulk_inventory"][-1]["tag"], "fermenting")

    def test_a_later_month_starts_where_this_one_ended(self):
        sep = calc.ttb_report(self.batches, "2026-09-01", "2026-09-30")
        self.assertEqual(sep["production_gal"], 0.0)
        self.assertEqual(sep["removals"], {})
        self.assertEqual(sep["begin"]["bulk_gal"], 5.8)
        self.assertEqual(sep["begin"]["bottled_gal"], round(17 * BOTTLE, 2))
        self.assertEqual(sep["bottled_inventory"][0]["units"], 17)

    def test_every_month_balances_and_carries(self):
        assert_books(self, self.batches)

    def test_unit_gallons_reads_the_package(self):
        for text, want in [("750 ml", BOTTLE), ("1.5 L", 1.5 * GPL),
                           ("1,5 L", 1.5 * GPL), ("2 liters", 2 * GPL),
                           ("12 oz", 12 / 128), ("12 fl oz", 12 / 128),
                           ("5 gallons", 5.0), ("1,000 ml", GPL)]:
            self.assertAlmostEqual(calc.unit_gallons(text), want, msg=text)
        self.assertIsNone(calc.unit_gallons("bottle"))

    def test_an_unknown_abv_is_a_gap_not_a_crash(self):
        b = august_batch()
        b["readings"] = []
        rep = calc.ttb_report([b], "2026-08-01", "2026-08-31")
        self.assertTrue(any("can't be estimated" in g for g in rep["gaps"]))

    def test_an_unsized_package_is_a_gap_and_still_balances(self):
        b = august_batch()
        b["packaging"]["unit"] = "bottle"       # states no volume
        rep = calc.ttb_report([b], "2026-08-01", "2026-08-31")
        self.assertTrue(any("states no volume" in g for g in rep["gaps"]))
        self.assertTrue(rep["balance"]["ok"])

    def test_other_removals_are_not_taxed_silently(self):
        b = august_batch()
        b["dispositions"].append({"at": "2026-08-27T12:00", "kind": "other",
                                  "qty": 2})
        rep = calc.ttb_report([b], "2026-08-01", "2026-08-31")
        self.assertIn("other — classify", rep["removals"])
        self.assertEqual(rep["taxable_removals_gal"], round(10 * BOTTLE, 2))
        self.assertTrue(any("classify before filing" in g for g in rep["gaps"]))

    def test_a_backwards_or_bad_period_is_refused(self):
        with self.assertRaisesRegex(ValueError, "after it ends"):
            calc.ttb_report(self.batches, "2026-09-01", "2026-08-01")
        with self.assertRaisesRegex(ValueError, "isn't a date"):
            calc.ttb_report(self.batches, "08/01/2026", "2026-08-31")


class TaxClassTest(unittest.TestCase):
    def batch(self, og, fg, **extra):
        b = {"id": "B-2026-009", "measured": {"og": og},
             "readings": [{"at": "2026-08-14T09:00", "sg": fg}]}
        b.update(extra)
        return b

    def test_the_owners_fourteen_percent_is_under_sixteen(self):
        cls, lo, hi, warn = calc.wine_tax_class(self.batch(1.1067, 1.000))
        self.assertEqual(cls, "still ≤16 %")
        self.assertEqual(lo, 14.0)
        self.assertIsNone(warn)
        # finishing a touch below 1.000 the estimates are 14.3-15.6 % — both
        # under 16, so the class isn't in doubt and nothing is flagged
        self.assertIsNone(calc.wine_tax_class(self.batch(1.1067, 0.998))[3])

    def test_an_estimate_across_a_line_is_flagged_not_guessed(self):
        # the simple formula says 14.7 %; the fuller one says 16.2 % — the
        # class follows the label estimate, and the report asks for a lab ABV
        cls, lo, hi, warn = calc.wine_tax_class(self.batch(1.112, 1.000))
        self.assertLess(lo, 16)
        self.assertGreater(hi, 16)
        self.assertEqual(cls, "still ≤16 %")
        self.assertIn("lab measurement", warn)

    def test_a_lab_abv_settles_the_class(self):
        b = self.batch(1.112, 1.000,
                       packaging={"at": "2026-08-20T10:00", "units": 28,
                                  "unit": "750 ml", "abv_measured": 16.4})
        cls, lo, hi, warn = calc.wine_tax_class(b)
        self.assertEqual((cls, lo, warn), ("still 16–21 %", 16.4, None))

    def test_a_sack_mead_is_sixteen_to_twentyone_and_asks_for_a_lab(self):
        # simple 18.4 %; the fuller formula overshoots to 21.7 % this high —
        # neither number is good enough at the 21 % line, so it asks
        cls, lo, hi, warn = calc.wine_tax_class(self.batch(1.150, 1.010))
        self.assertEqual(cls, "still 16–21 %")
        self.assertIn("21 % line", warn)

    def test_sweetening_does_not_lower_the_class(self):
        b = self.batch(1.1067, 1.000,
                       sweetenings=[{"at": "2026-08-20T09:00", "to_sg": 1.020}])
        self.assertEqual(calc.wine_tax_class(b)[1], 14.0)   # from the reading

    def test_bottle_conditioned_past_the_still_limit_is_sparkling(self):
        b = self.batch(1.090, 1.000, primings=[{"target_vols": 2.5}])
        self.assertEqual(calc.wine_tax_class(b)[0], "sparkling / carbonated")


class BooksThroughTheStoreTest(unittest.TestCase):
    """A batch made the real way — through the store's guarded methods —
    racked in one month and bottled the next: the case the first version of
    the report got wrong in both months."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-ttb-"))
        self.addCleanup(shutil.rmtree, self.root)
        s = self.store = Store(self.root)
        dispatch(Request("POST", "/recipes", {},
                         {"gal": "6", "abv": "14", "og": "", "fg": "1.000",
                          "yeast": "71B", "demand": "medium", "additions": "4",
                          "name": "OB"}, (), s))
        dispatch(Request("POST", "/recipes/ob/must", {},
                         {"gal": "6", "id": "B-2026-001",
                          "pitched_at": "2026-07-30T10:00", "volume_gal": "6",
                          "honey_lb": "18.29", "water_gal": "4.48",
                          "yeast_g": "10", "goferm_g": "12.5", "og": "1.1067",
                          "ph": "3.9", "cal_f": "60"}, (), s))
        bid = "B-2026-001"
        s.add_reading(bid, "1.000", at="2026-08-18T09:00")
        s.add_reading(bid, "1.000", at="2026-08-21T09:00")
        s.record_racking(bid, "5.7", at="2026-08-24T09:00")
        s.record_stabilize(bid, "3.6", at="2026-08-26T09:00")
        s.record_bottling(bid, "28", "750 ml", at="2026-09-08T10:00")
        s.record_disposition(bid, "sold", "10", "Cork & Keg", at="2026-09-18T12:00")
        s.record_disposition(bid, "sample", "2", at="2026-09-23T12:00")
        s.record_disposition(bid, "taproom", "6", at="2026-10-03T12:00")
        s.record_disposition(bid, "breakage", "1", at="2026-10-05T12:00")
        self.batches = s.list_batches()

    def test_every_month_balances_and_carries(self):
        assert_books(self, self.batches)

    def test_the_racking_loss_lands_in_august_and_the_fill_loss_in_september(self):
        aug = calc.ttb_report(self.batches, "2026-08-01", "2026-08-31")
        sep = calc.ttb_report(self.batches, "2026-09-01", "2026-09-30")
        self.assertEqual([(x["why"], x["gal"]) for x in aug["losses"]],
                         [("racking", 0.3)])
        self.assertEqual([x["why"] for x in sep["losses"]], ["bottling"])
        self.assertAlmostEqual(sep["losses"][0]["gal"], 5.7 - 28 * BOTTLE,
                               places=3)
        self.assertEqual(self.store.load_batch("B-2026-001")["packaging"]
                         ["tax_class"], "still ≤16 %")


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

    def test_page_leads_with_the_balance_then_the_sections(self):
        r = self.get("/ttb", {"start": "2026-08-01", "end": "2026-08-31"})
        self.assertEqual(r.status, 200)
        self.assertIn("The books balance for this period", r.body)
        for heading in ("Produced by fermentation", "Bottled", "Removals",
                        "Losses", "On hand at the end", "Drawn from bulk"):
            self.assertIn(heading, r.body)
        self.assertIn("B-2026-001", r.body)

    def test_a_bad_date_is_a_banner_not_a_crash(self):
        r = self.get("/ttb", {"start": "08/01/2026", "end": "2026-08-31"})
        self.assertEqual(r.status, 200)
        self.assertIn("showing this month instead", r.body)
        r = self.post("/ttb/export", {"start": "2026/08/01", "end": "x"})
        self.assertEqual(r.status, 303)
        self.assertIn("isn't a date", unquote(r.location))

    def test_export_writes_a_markdown_file(self):
        r = self.post("/ttb/export", {"start": "2026-08-01",
                                      "end": "2026-08-31"})
        self.assertEqual(r.status, 303)
        report = self.root / "reports" / "ttb-2026-08-01-to-2026-08-31.md"
        self.assertTrue(report.exists())
        text = report.read_text()
        for line in ("both sections balance", "Produced by fermentation",
                     "Removals", "drawn from 5.9 gal bulk"):
            self.assertIn(line, text)
        # a derived report states it computes no tax
        self.assertIn("no tax", text.lower())


class AbvAfterSweeteningTest(BooksThroughTheStoreTest):
    def test_the_batch_page_abv_does_not_drop_when_sweetened(self):
        # the store-built batch is dry at 1.000 from OG 1.1067: 14 %. Make a
        # fresh one and sweeten it — sugar goes in, alcohol does not go down
        s = self.store
        dispatch(Request("POST", "/recipes/ob/must", {},
                         {"gal": "6", "id": "B-2026-002",
                          "pitched_at": "2026-08-01T10:00", "volume_gal": "6",
                          "og": "1.1067", "cal_f": "60"}, (), s))
        s.add_reading("B-2026-002", "1.000", at="2026-08-20T09:00")
        s.add_reading("B-2026-002", "1.000", at="2026-08-23T09:00")
        s.record_stabilize("B-2026-002", "3.5", at="2026-08-25T09:00")
        s.record_backsweeten("B-2026-002", "1.020", at="2026-08-26T09:00")
        page = dispatch(Request("GET", "/batches/B-2026-002", {}, {}, (),
                                s)).body
        self.assertIn('<span class="l">Now</span><span class="n">1.020</span>',
                      page)
        self.assertIn('<span class="l">ABV so far</span><span class="n">14 %',
                      page)


if __name__ == "__main__":
    unittest.main()
