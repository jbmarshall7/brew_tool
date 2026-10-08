"""Round 11: it refuses the dangerous thing.

Bottling and priming each answer to ONE rule in calc (bottling_refusal,
priming_refusal), enforced by the store and explained by the form, so the two
can never disagree. A bottled batch's record is closed; nothing is dated
before its pitch or in the future; a form that arrives twice writes once; two
writes at the same moment both land; and the sulfite dose has a ceiling and
a legal limit. Dates here are relative to now, so nothing ages out.
"""
import re
import shutil
import sys
import tempfile
import threading
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew import calc
from brew.server import Request, dispatch
from brew.store import Store

NOW = datetime.now().replace(second=0, microsecond=0)


def ago(days, hour=9):
    return (NOW - timedelta(days=days)).replace(hour=hour, minute=0) \
        .strftime("%Y-%m-%dT%H:%M")


OWNER = {"gal": "6", "abv": "14", "og": "", "fg": "1.000", "yeast": "71B",
         "demand": "medium", "additions": "4", "name": "OB"}


def token():
    return uuid.uuid4().hex


class GuardrailCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-guard-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)
        self.post("/recipes", OWNER)
        self.post("/recipes/ob/must", self.must_form())
        self.bid = f"B-{(NOW - timedelta(days=40)).year}-001"

    @staticmethod
    def must_form(**over):
        f = {"gal": "6", "id": "1", "pitched_at": ago(40), "volume_gal": "6",
             "honey_lb": "18.29", "water_gal": "4.48", "yeast_g": "10",
             "goferm_g": "12.5", "og": "1.1067", "ph": "3.9", "cal_f": "60"}
        f.update(over)
        return f

    def post(self, path, form):
        return dispatch(Request("POST", path, {}, form, (), self.store))

    def get(self, path, params=None):
        return dispatch(Request("GET", path, params or {}, {}, (), self.store))

    def b(self):
        return self.store.load_batch(self.bid)

    def reads(self, *pairs):
        for days, g in pairs:
            self.store.add_reading(self.bid, g, at=ago(days))

    def active(self):           # 20 points down overnight: still working
        self.reads((10, "1.080"), (9, "1.060"))

    def finished(self):         # dry, and flat for four days
        self.reads((10, "1.000"), (6, "1.000"))

    def stuck_sweet(self):      # flat for a week — at 1.030, not 1.000
        self.reads((10, "1.031"), (6, "1.030"), (3, "1.030"))

    def refused(self, r):
        return "kind=err" in (r.location or "")


class BottlingTest(GuardrailCase):
    def test_an_active_ferment_is_refused(self):
        self.active()
        with self.assertRaisesRegex(ValueError, "steady gravity"):
            self.store.record_bottling(self.bid, "28", "750 ml")
        self.assertNotIn("packaging", self.b())

    def test_stuck_sweet_with_live_yeast_is_refused(self):
        self.stuck_sweet()
        with self.assertRaisesRegex(ValueError, "Stabilize it first"):
            self.store.record_bottling(self.bid, "28", "750 ml")

    def test_sweetened_but_not_stabilized_is_refused(self):
        self.finished()
        self.store.record_backsweeten(self.bid, "1.015",
                                      override_reason="keg, force-carbonated")
        with self.assertRaisesRegex(ValueError, "without being stabilized"):
            self.store.record_bottling(self.bid, "28", "750 ml")

    def test_dry_and_steady_bottles_without_stabilizing(self):
        self.finished()
        self.store.record_bottling(self.bid, "28", "750 ml")
        self.assertNotIn("override", self.b()["packaging"])

    def test_stabilized_bottles_even_sweet(self):
        self.finished()
        self.store.record_stabilize(self.bid, "3.4")
        self.store.record_backsweeten(self.bid, "1.015")
        self.store.record_bottling(self.bid, "28", "750 ml")

    def test_a_recorded_reason_overrides_and_is_kept(self):
        self.active()
        self.store.record_bottling(self.bid, "4", "keg",
                                   override_reason="kegged and kept at 34 °F")
        self.assertEqual(self.b()["packaging"]["override"],
                         "kegged and kept at 34 °F")

    def test_the_route_refuses_and_the_form_explains(self):
        self.active()
        r = self.post(f"/batches/{self.bid}/bottle",
                      {"units": "28", "unit": "750 ml"})
        self.assertTrue(self.refused(r))
        page = self.get(f"/batches/{self.bid}").body
        self.assertIn("steady gravity", page)            # the rule's own words
        self.assertIn("Bottle it anyway", page)          # the override
        self.assertIn('name="override"', page)


class PrimingTest(GuardrailCase):
    def test_stuck_sweet_is_not_dry_so_priming_is_refused(self):
        self.stuck_sweet()
        self.store.record_racking(self.bid, "5.8", at=ago(2))
        with self.assertRaisesRegex(ValueError, "not dry"):
            self.store.record_priming(self.bid, "2.5", "68")
        self.assertIsNone(self.b().get("primings"))

    def test_the_refusal_says_how_much_pressure(self):
        self.stuck_sweet()
        text = calc.priming_refusal(self.b())
        # 30 points left x ~0.67 volumes a point: ~20 volumes on top
        self.assertIn("30 points", text)
        self.assertIn("20.2 more volumes", text)

    def test_a_second_priming_is_refused(self):
        self.finished()
        self.store.record_priming(self.bid, "2.5", "68")
        with self.assertRaisesRegex(ValueError, "already primed"):
            self.store.record_priming(self.bid, "2.5", "68")
        self.assertEqual(len(self.b()["primings"]), 1)

    def test_a_sweetened_mead_is_refused(self):
        self.finished()
        self.store.record_backsweeten(self.bid, "1.010",
                                      override_reason="testing the rule")
        with self.assertRaisesRegex(ValueError, "back-sweetened"):
            self.store.record_priming(self.bid, "2.5", "68")

    def test_dry_and_steady_primes_and_then_bottles(self):
        self.finished()
        self.store.record_priming(self.bid, "2.5", "68")
        self.store.record_bottling(self.bid, "24", "750 ml")
        self.assertTrue(self.b()["packaging"]["conditioned"])

    def test_a_sweet_target_fg_does_not_make_sugar_safe(self):
        # designed sweet (FG 1.015) and sitting there: still 15 points of
        # sugar that live yeast can find once it is sealed in with priming
        b = self.b()
        b["target"]["fg"] = 1.015
        self.store.save_batch(b)
        self.reads((10, "1.015"), (6, "1.015"))
        self.assertFalse(calc.is_dry(self.b()))
        self.assertIn("not dry", calc.priming_refusal(self.b()))


class ClosedAfterBottlingTest(GuardrailCase):
    def setUp(self):
        super().setUp()
        self.finished()
        self.store.record_bottling(self.bid, "28", "750 ml", at=ago(2))

    def test_nothing_more_goes_in(self):
        for what, call in [
            ("a reading", lambda: self.store.add_reading(self.bid, "1.000")),
            ("a racking", lambda: self.store.record_racking(self.bid, "2")),
            ("stabilize", lambda: self.store.record_stabilize(
                self.bid, "3.4", override_reason="x")),
            ("prime", lambda: self.store.record_priming(
                self.bid, "2.5", "68", override_reason="x")),
            ("sweeten", lambda: self.store.record_backsweeten(
                self.bid, "1.010", override_reason="x")),
            ("flavor", lambda: self.store.record_flavor(self.bid, "oak", "cubes")),
        ]:
            with self.assertRaisesRegex(ValueError, "is bottled", msg=what):
                call()

    def test_tastings_and_dispositions_are_still_welcome(self):
        stage = calc.TASTING_STAGES[-1]
        self.store.record_tasting(self.bid, stage, 4, "honeyed, long finish")
        self.store.record_disposition(self.bid, "sold", "6", "Cork & Keg")
        self.assertEqual(calc.units_on_hand(self.b()), 22)

    def test_the_page_stops_offering_what_it_would_refuse(self):
        page = self.get(f"/batches/{self.bid}").body
        for gone in ('id="log"', 'href="#log"', f'/batches/{self.bid}/rack"',
                     f'/batches/{self.bid}/flavor"', "I gave this"):
            self.assertNotIn(gone, page, gone)
        self.assertIn(f'/batches/{self.bid}/disposition"', page)
        self.assertIn(f'/batches/{self.bid}/tasting"', page)
        today = self.get("/").body
        self.assertNotIn(f'action="/batches/{self.bid}/reading"', today)


class DatingTest(GuardrailCase):
    def test_nothing_before_the_pitch(self):
        with self.assertRaisesRegex(ValueError, "before it was pitched"):
            self.store.add_reading(self.bid, "1.050", at=ago(45))

    def test_nothing_in_the_future(self):
        later = (NOW + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
        with self.assertRaisesRegex(ValueError, "in the future"):
            self.store.add_reading(self.bid, "1.050", at=later)

    def test_no_sale_before_the_bottling(self):
        self.finished()
        self.store.record_bottling(self.bid, "28", "750 ml", at=ago(2))
        with self.assertRaisesRegex(ValueError, "before it was bottled"):
            self.store.record_disposition(self.bid, "sold", "6", at=ago(4))

    def test_a_future_pitch_is_refused_and_keeps_what_was_typed(self):
        future = (NOW + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M")
        r = self.post("/recipes/ob/must", self.must_form(id="2", pitched_at=future))
        self.assertTrue(self.refused(r))
        self.assertIn("in the future", unquote(r.location))
        self.assertIn("honey_lb=18.29", r.location)      # nothing retyped
        self.assertEqual(len(self.store.list_batches()), 1)


class OnceTest(GuardrailCase):
    def test_a_double_tapped_sale_counts_once(self):
        self.finished()
        self.store.record_bottling(self.bid, "28", "750 ml", at=ago(2))
        form = {"kind": "sold", "qty": "12", "to": "Cork & Keg", "once": token()}
        first = self.post(f"/batches/{self.bid}/disposition", form)
        second = self.post(f"/batches/{self.bid}/disposition", form)
        self.assertFalse(self.refused(first))
        self.assertIn("Already recorded", unquote(second.location))
        self.assertEqual(len(self.b()["dispositions"]), 1)
        self.assertEqual(calc.units_on_hand(self.b()), 16)

    def test_a_second_real_sale_is_never_blocked(self):
        self.finished()
        self.store.record_bottling(self.bid, "28", "750 ml", at=ago(2))
        for _ in range(2):           # a fresh page, a fresh token
            self.post(f"/batches/{self.bid}/disposition",
                      {"kind": "sold", "qty": "12", "once": token()})
        self.assertEqual(calc.units_on_hand(self.b()), 4)

    def test_a_double_tapped_reading_and_must_write_once(self):
        form = {"reading": "1.050", "once": token()}
        self.post(f"/batches/{self.bid}/reading", form)
        self.post(f"/batches/{self.bid}/reading", form)
        self.assertEqual(len(self.b()["readings"]), 1)
        must = self.must_form(id="2", once=token())
        self.post("/recipes/ob/must", must)
        again = self.post("/recipes/ob/must", must)
        self.assertEqual(again.location.split("?")[0],
                         f"/batches/B-{(NOW - timedelta(days=40)).year}-002")
        self.assertIn("Already recorded", unquote(again.location))
        self.assertEqual(len(self.store.list_batches()), 2)

    def test_a_double_tapped_permit_is_added_once(self):
        form = {"label": "TTB Basic Permit", "expires": "2030-01-01",
                "once": token()}
        self.post("/documents/add", form)
        self.post("/documents/add", form)
        self.assertEqual(len(self.store.list_documents()), 1)

    def test_every_recording_form_carries_a_token(self):
        # parse the rendered forms, so a new form can't ship without one
        self.finished()
        self.store.record_racking(self.bid, "5.8", at=ago(1))
        page = self.get(f"/batches/{self.bid}",
                        {"stab_ph": "3.4", "prime_vols": "2.5",
                         "prime_temp": "68", "sweeten_to": "1.010"}).body
        page += self.get("/").body + self.get("/vessels").body
        page += self.get("/documents").body
        page += self.get("/recipes/ob/must", {"gal": "6"}).body
        forms = re.findall(r'<form[^>]*method="post"[^>]*>.*?</form>', page,
                           re.S)
        exempt = ("/pull-flavor", "/vessel\"", "/renew", "/ttb/export")
        checked = [f for f in forms if not any(x in f for x in exempt)]
        self.assertGreaterEqual(len(checked), 9)
        for f in checked:
            self.assertIn('name="once"', f, f[:90])


class ConcurrencyTest(GuardrailCase):
    def test_twenty_readings_at_once_all_land(self):
        def tap():
            self.post(f"/batches/{self.bid}/reading",
                      {"reading": "1.050", "once": token()})
        threads = [threading.Thread(target=tap) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(self.b()["readings"]), 20)


class SulfiteTest(GuardrailCase):
    def test_the_tiers(self):
        def tier(ph):
            free, _ = calc.molecular_so2_free_needed(ph)
            p = calc.sulfite_problem(free, ph)
            return p and p[0]
        self.assertIsNone(tier(3.6))
        self.assertEqual(tier(3.85), "warn")
        self.assertEqual(tier(4.0), "reason")      # ~125 ppm free
        self.assertEqual(tier(4.5), "refuse")      # ~393 ppm, over 350 total

    def test_past_the_ceiling_needs_a_reason(self):
        self.finished()
        with self.assertRaisesRegex(ValueError, "Record a reason"):
            self.store.record_stabilize(self.bid, "4.0")
        self.store.record_stabilize(self.bid, "4.0",
                                    override_reason="acid on order; dosing now")

    def test_past_the_legal_limit_no_reason_will_do(self):
        self.finished()
        with self.assertRaisesRegex(ValueError, "350 ppm legal limit"):
            self.store.record_stabilize(self.bid, "4.5",
                                        override_reason="I insist")
        self.assertIsNone(self.b().get("stabilizations"))

    def test_the_preview_refuses_before_anything_is_recorded(self):
        self.finished()
        page = self.get(f"/batches/{self.bid}", {"stab_ph": "4.5"}).body
        self.assertIn("350 ppm legal limit", page)
        self.assertNotIn(f'/batches/{self.bid}/stabilize"', page)


class RulesTest(unittest.TestCase):
    def test_a_point_of_sugar_is_about_two_thirds_of_a_volume(self):
        self.assertAlmostEqual(calc.VOLS_PER_POINT, 0.67, places=2)

    def test_the_records_never_go_in_the_public_repo(self):
        ignore = (Path(__file__).resolve().parent.parent / ".gitignore")
        self.assertIn("data/", ignore.read_text().split())


if __name__ == "__main__":
    unittest.main()
