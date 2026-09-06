"""The fermentation log: one gravity in, three columns out, and the one
sentence saying what to do about it.

The next-action rules are the product, so each gets its own case with an
injected clock — nothing here depends on the day the suite runs.
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

NOW = datetime(2026, 9, 6, 10, 0)
OWNER = {"gal": "6", "abv": "14", "og": "", "fg": "1.000", "yeast": "71B",
         "demand": "medium", "additions": "4",
         "name": "Orange Blossom Traditional", "honey": "orange blossom"}
RECORD = {"gal": "6", "id": "B-2026-003", "pitched_at": "2026-09-03T15:40",
          "volume_gal": "6", "honey_lb": "18.3", "water_gal": "4.5",
          "yeast_g": "10", "goferm_g": "12.5", "og": "1.1029", "ph": "3.9",
          "reading": "1.101", "temp_f": "76", "cal_f": "60"}
MUST = "/recipes/orange-blossom-traditional/must"


def batch(pitched="2026-09-03T15:40", readings=(), og=1.1029, fg=1.0,
          stop=1.069, due=(), feeds=()):
    """A batch shaped like the file, built straight so a rule can be aimed at."""
    return {
        "id": "B-2026-003", "pitched_at": pitched,
        "measured": {"og": og}, "target": {"og": 1.1067, "fg": fg},
        "nutrients": {"stop_sg": stop, "product": "fermaid-o",
                      "additions": [{"n": i + 1, "g": 6.3, "due": d,
                                     "stop_sg": stop, "rule": "24 h"}
                                    for i, d in enumerate(due)]},
        "readings": [{"at": a, "sg": s, "reading": s, "sample_f": 68,
                      "cal_f": 60, "note": ""} for a, s in readings],
        "feeds": [{"n": n, "at": "2026-09-0%dT16:00" % (n + 3), "g": 6.3,
                   "note": ""} for n in feeds],
    }


def act(b):
    return calc.next_action(b, NOW, "Fermaid O")


class GravityTextTest(unittest.TestCase):
    def test_keeps_a_significant_fourth_decimal(self):
        # the digit the must-day correction turns on must survive
        self.assertEqual(calc.sg_text(1.1029), "1.1029")
        self.assertEqual(calc.sg_text(1.1067), "1.1067")
        # ...but a gravity that is only three deep stays three deep
        self.assertEqual(calc.sg_text(1.030), "1.030")
        self.assertEqual(calc.sg_text(1.0), "1.000")
        self.assertEqual(calc.sg_text(0.998), "0.998")
        self.assertEqual(calc.sg_text(None), "—")


class LedgerTest(unittest.TestCase):
    def test_one_number_in_three_columns_out(self):
        rows = calc.ledger(1.104, "2026-08-20T15:00",
                           [{"at": "2026-09-04T09:20", "sg": 1.041}])
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r["day"], 15)                  # Aug 20 → Sep 4
        self.assertEqual(r["abv"], 8.27)                # (1.104-1.041)*131.25
        self.assertEqual(r["atten"], 61)                # .063/.104
        self.assertIsNone(r["drop"])                    # nothing to compare

    def test_drop_is_points_since_the_previous_reading(self):
        rows = calc.ledger(1.1029, "2026-09-03T15:40",
                           [{"at": "2026-09-06T09:00", "sg": 1.0708},
                            {"at": "2026-09-11T09:00", "sg": 1.0418}])
        self.assertEqual([r["drop"] for r in rows], [None, 29.0])
        self.assertEqual([r["day"] for r in rows], [3, 8])

    def test_out_of_order_readings_are_sorted(self):
        rows = calc.ledger(1.100, "2026-09-01T09:00",
                           [{"at": "2026-09-05T09:00", "sg": 1.050},
                            {"at": "2026-09-03T09:00", "sg": 1.080}])
        self.assertEqual([r["sg"] for r in rows], [1.080, 1.050])
        self.assertEqual(rows[1]["drop"], 30.0)

    def test_attenuation_of_a_must_that_has_not_moved(self):
        self.assertEqual(calc.attenuation(1.100, 1.100), 0)
        self.assertEqual(calc.attenuation(1.000, 1.000), 0)   # no span


class NextActionTest(unittest.TestCase):
    DUE = ["2026-09-04T15:40", "2026-09-05T15:40", "2026-09-06T15:40",
           "2026-09-10T15:40"]

    def test_1_a_feeding_owed_outranks_everything(self):
        # nothing logged: the first one is two days late and says so
        a = act(batch(due=self.DUE))
        self.assertEqual(a["kind"], "warn")
        self.assertIn("Fermaid O #1, 6.3 g — was due Fri Sep 4, 3:40 pm, "
                      "2 days ago", a["text"])
        self.assertIn("Stop at SG 1.069", a["text"])

    def test_1_a_logged_feeding_drops_out(self):
        a = act(batch(due=self.DUE, feeds=(1, 2)))
        self.assertIn("Fermaid O #3, 6.3 g — due today at 3:40 pm", a["text"])
        # all four in: the schedule has nothing left to say
        a = act(batch(due=self.DUE, feeds=(1, 2, 3),
                      readings=[("2026-09-06T09:00", 1.085)]))
        self.assertNotIn("due", a["text"])
        self.assertIn("Next up: Fermaid O #4", a["text"])

    def test_1_the_last_feeding_is_never_nagged_once_given(self):
        b = batch(due=self.DUE, feeds=(1, 2, 3, 4),
                  readings=[("2026-09-06T09:00", 1.085)])
        self.assertEqual(calc.next_feed(b, NOW), (None, False))
        self.assertNotIn("Fermaid O", act(b)["text"])

    def test_1_no_feeding_is_named_once_past_the_break(self):
        # nothing is fed after a third of the sugar is gone, whatever the
        # calendar says
        b = batch(readings=[("2026-09-05T08:00", 1.075),
                            ("2026-09-06T08:00", 1.060)],
                  due=["2026-09-06T15:40"])
        self.assertNotIn("due today", act(b)["text"])
        self.assertEqual(calc.next_feed(b, NOW), (None, True))

    def test_2_finished_needs_only_one_reading(self):
        a = act(batch("2026-08-01T09:00", [("2026-09-04T09:00", 1.001)]))
        self.assertEqual(a["kind"], "ok")
        self.assertIn("1.001 and steady at 13.4 %", a["text"])
        self.assertIn("rack it off the lees", a["text"])

    def test_3_a_rise_is_the_glass_not_the_mead(self):
        a = act(batch("2026-08-25T09:00", [("2026-09-02T09:00", 1.030),
                                           ("2026-09-05T09:00", 1.034)]))
        self.assertEqual(a["kind"], "warn")
        self.assertIn("reads 4 points higher than last time", a["text"])
        self.assertIn("usually the glass, not the mead", a["text"])

    def test_4_stuck_is_a_day_with_nothing_to_show(self):
        a = act(batch("2026-08-01T09:00", [("2026-09-02T09:00", 1.0305),
                                           ("2026-09-04T09:00", 1.030)]))
        self.assertEqual(a["kind"], "warn")
        self.assertIn("Stuck at 1.030 — no movement in 2 days", a["text"])
        self.assertIn("warm it and rouse it", a["text"])

    def test_5_never_claims_movement_from_one_reading(self):
        for b in (batch("2026-09-06T09:00"),
                  batch("2026-09-06T09:00", [("2026-09-06T09:00", 1.1029)]),
                  batch("2026-09-01T09:00", [("2026-09-02T09:00", 1.090)])):
            text = act(b)["text"]
            self.assertNotIn("points down", text)
            self.assertNotIn("Stuck", text)

    def test_5_the_opening_says_which_day_it_is(self):
        self.assertIn("Pitched today at 1.1029",
                      act(batch("2026-09-06T09:00"))["text"])
        self.assertIn("Pitched at 1.1029, 5 days ago, and not read since",
                      act(batch("2026-09-01T09:00"))["text"])
        self.assertIn("Next up: Fermaid O #1, 6.3 g Mon Sep 7, 9:00 am",
                      act(batch("2026-09-06T09:00",
                                due=["2026-09-07T09:00"]))["text"])

    def test_6_a_week_unread(self):
        a = act(batch("2026-08-01T09:00", [("2026-08-20T09:00", 1.020)]))
        self.assertEqual(a["kind"], "warn")
        self.assertIn("Last read 17 days ago at 1.020", a["text"])

    def test_7_simply_working(self):
        a = act(batch("2026-08-25T09:00", [("2026-08-30T09:00", 1.047),
                                           ("2026-09-02T09:00", 1.041)]))
        self.assertEqual(a["kind"], "ok")
        self.assertIn("Last read 4 days ago at 1.041 — 6 points down in "
                      "3 days", a["text"])
        a = act(batch("2026-08-25T09:00", [("2026-09-03T09:00", 1.047),
                                           ("2026-09-06T08:00", 1.041)]))
        self.assertIn("6 points down — still moving", a["text"])


class LogTestCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-test-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)
        dispatch(Request("POST", "/recipes", {}, OWNER, (), self.store))
        dispatch(Request("POST", MUST, {}, RECORD, (), self.store))

    def get(self, path, params=None):
        return dispatch(Request("GET", path, params or {}, {}, (), self.store))

    def post(self, path, form):
        return dispatch(Request("POST", path, {}, form, (), self.store))

    def file(self):
        return json.loads(
            (self.root / "batches" / "B-2026-003.json").read_text())


class StoreReadingTest(LogTestCase):
    def test_stores_the_corrected_value_beside_the_raw_one(self):
        self.store.add_reading("B-2026-003", "1.070", "68", "60", "bubbling",
                               at="2026-09-06T09:00")
        r = self.file()["readings"][0]
        self.assertEqual(r["reading"], 1.07)      # what the glass said
        self.assertEqual(r["sg"], 1.0708)         # corrected for 68 °F
        self.assertEqual((r["sample_f"], r["cal_f"]), (68.0, 60.0))
        self.assertEqual(r["at"], "2026-09-06T09:00")
        self.assertEqual(r["note"], "bubbling")

    def test_blank_temperature_means_no_correction(self):
        self.store.add_reading("B-2026-003", "1.070", "", "",
                               at="2026-09-06T09:00")
        r = self.file()["readings"][0]
        self.assertEqual(r["sg"], 1.07)
        self.assertIsNone(r["sample_f"])
        self.assertEqual(r["cal_f"], 60)          # the app's default

    def test_readings_stay_in_order(self):
        self.store.add_reading("B-2026-003", "1.041", at="2026-09-11T09:00")
        self.store.add_reading("B-2026-003", "1.070", at="2026-09-06T09:00")
        self.assertEqual([r["at"] for r in self.file()["readings"]],
                         ["2026-09-06T09:00", "2026-09-11T09:00"])

    def test_a_nonsense_gravity_is_refused(self):
        with self.assertRaisesRegex(ValueError, "above 1.25"):
            self.store.add_reading("B-2026-003", "11.01")
        self.assertEqual(self.file().get("readings"), None)

    def test_two_readings_the_same_afternoon_stay_apart(self):
        self.store.add_reading("B-2026-003", "1.070", at="2026-09-06T09:00")
        self.store.add_reading("B-2026-003", "1.068", at="2026-09-06T16:30")
        self.assertEqual(len(self.file()["readings"]), 2)


class LogRouteTest(LogTestCase):
    def test_logging_lands_on_the_batch_with_what_it_means(self):
        r = self.post("/batches/B-2026-003/reading",
                      {"reading": "1.070", "sample_f": "68",
                       "note": "bubbling hard"})
        self.assertEqual(r.status, 303)
        self.assertTrue(r.location.startswith("/batches/B-2026-003?msg="))
        for piece in ("Logged%201.0708", "read%201.070%20at%2068%20%C2%B0F",
                      "day%203", "so%20far", "attenuated"):
            self.assertIn(piece, r.location, piece)
        self.assertEqual(len(self.file()["readings"]), 1)

    def test_the_banner_names_the_derived_figures(self):
        self.store.add_reading("B-2026-003", "1.070", at="2026-09-06T09:00")
        r = self.post("/batches/B-2026-003/reading", {"reading": "1.041"})
        from urllib.parse import parse_qs, urlparse
        msg = parse_qs(urlparse(r.location).query)["msg"][0]
        self.assertIn("29 points down", msg)
        self.assertIn("8.1 % so far", msg)      # (1.1029 − 1.041) × 131.25
        self.assertIn("60 % attenuated", msg)   # .0619 ÷ .1029

    def test_a_bad_gravity_keeps_what_was_typed(self):
        r = self.post("/batches/B-2026-003/reading",
                      {"reading": "11.01", "note": "hazy"})
        self.assertEqual(r.status, 303)
        self.assertIn("reading=11.01", r.location)
        self.assertIn("note=hazy", r.location)
        self.assertIn("kind=err", r.location)
        self.assertEqual(r.location.split("?")[0], "/batches/B-2026-003")
        self.assertIsNone(self.file().get("readings"))


class BatchPageTest(LogTestCase):
    def test_the_log_form_is_open_and_the_ledger_derives(self):
        self.store.add_reading("B-2026-003", "1.070", "68", at="2026-09-06T09:00")
        self.store.add_reading("B-2026-003", "1.041", "68", at="2026-09-11T09:00")
        body = self.get("/batches/B-2026-003").body
        self.assertIn('id="log"', body)
        self.assertIn("<button>Log it</button>", body)
        for cell in ("1.0708", "1.0418", "29 pts", "8 %", "59 %",
                     "Sun Sep 6, 9:00 am"):
            self.assertIn(cell, body, cell)
        self.assertIn("one gravity in, three columns out", body)
        # newest first
        self.assertLess(body.index("1.0418"), body.index("1.0708"))

    def test_the_stats_strip_and_the_next_sentence(self):
        self.store.add_reading("B-2026-003", "1.041", at="2026-09-11T09:00")
        body = self.get("/batches/B-2026-003").body
        self.assertIn(">Now<", body)
        self.assertIn(">ABV so far<", body)
        self.assertIn(">Attenuated<", body)
        self.assertIn('<div class="nextbar">', body)
        self.assertIn("8.1 %", body)          # (1.1029-1.041)*131.25

    def test_only_the_next_feed_reads_as_due(self):
        body = self.get("/batches/B-2026-003").body
        self.assertLessEqual(body.count('pill warn">due'), 1)

    def test_an_old_batch_file_with_no_readings_still_renders(self):
        doc = self.file()
        self.assertNotIn("readings", doc)      # round 1 wrote none
        body = self.get("/batches/B-2026-003").body
        self.assertIn("No readings yet", body)
        self.assertIn('id="log"', body)


class FeedLogTest(LogTestCase):
    def test_recording_a_feed_is_an_event_not_a_tick(self):
        b, planned = self.store.record_feed("B-2026-003", "1",
                                            at="2026-09-04T16:00",
                                            note="stirred in")
        f = self.file()["feeds"][0]
        self.assertEqual(f["n"], 1)
        self.assertEqual(f["at"], "2026-09-04T16:00")
        self.assertEqual(f["g"], 6.3)          # copied from the schedule
        self.assertEqual(f["note"], "stirred in")
        self.assertEqual(planned["n"], 1)

    def test_the_same_feeding_cannot_be_logged_twice(self):
        self.store.record_feed("B-2026-003", "2")
        with self.assertRaisesRegex(ValueError, "already logged"):
            self.store.record_feed("B-2026-003", "2")
        self.assertEqual(len(self.file()["feeds"]), 1)

    def test_a_feeding_that_is_not_on_the_schedule_is_refused(self):
        with self.assertRaisesRegex(ValueError, "no feeding #9"):
            self.store.record_feed("B-2026-003", "9")
        self.assertIsNone(self.file().get("feeds"))

    def test_the_route_lands_with_what_is_next(self):
        r = self.post("/batches/B-2026-003/feed", {"n": "1"})
        self.assertEqual(r.status, 303)
        self.assertIn("Logged%20Fermaid%20O%20%231", r.location)
        self.assertIn("6.3%20g", r.location)
        self.assertEqual(len(self.file()["feeds"]), 1)

    def test_a_double_tap_says_so_and_writes_nothing(self):
        self.post("/batches/B-2026-003/feed", {"n": "1"})
        r = self.post("/batches/B-2026-003/feed", {"n": "1"})
        self.assertIn("already%20logged", r.location)
        self.assertIn("kind=err", r.location)
        self.assertEqual(len(self.file()["feeds"]), 1)

    def test_the_row_offers_the_button_then_shows_when_it_went_in(self):
        body = self.get("/batches/B-2026-003").body
        self.assertIn("<button class=\"quiet\">I gave this</button>", body)
        self.store.record_feed("B-2026-003", "1", at="2026-09-04T16:00")
        body = self.get("/batches/B-2026-003").body
        self.assertIn('pill ok">given', body)
        self.assertIn("Fri Sep 4, 4:00 pm", body)


class CellarListTest(LogTestCase):
    def test_lists_every_batch_with_what_it_wants(self):
        self.store.add_reading("B-2026-003", "1.041", at="2026-09-11T09:00")
        body = self.get("/batches").body
        self.assertIn('href="/batches/B-2026-003"', body)
        self.assertIn("Orange Blossom Traditional", body)
        self.assertIn("1.041", body)
        self.assertIn("keep up to date", body)      # the footer promise

    def test_empty_cellar_points_at_the_design_page(self):
        for f in (self.root / "batches").glob("*.json"):
            f.unlink()
        body = self.get("/batches").body
        self.assertIn("No musts recorded yet", body)
        self.assertIn('href="/"', body)


if __name__ == "__main__":
    unittest.main()
