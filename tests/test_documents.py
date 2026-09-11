"""Compliance documents: the derived status, the flat-file store, the page,
renewal, and the banner Today raises before a permit lapses. Only the expiry
date is stored; everything the tests check about urgency is computed from it.
"""
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew import calc
from brew.server import Request, dispatch
from brew.store import Store

TODAY = date(2026, 9, 11)


def on(days):
    """An ISO date `days` from TODAY (negative for the past)."""
    return (TODAY + timedelta(days=days)).isoformat()


class DocMathTest(unittest.TestCase):
    def test_days_left_counts_from_today(self):
        self.assertEqual(calc.doc_days_left(on(30), TODAY), 30)
        self.assertEqual(calc.doc_days_left(on(-3), TODAY), -3)
        self.assertIsNone(calc.doc_days_left("whenever", TODAY))

    def test_state_buckets(self):
        docs = [
            {"id": "D-001", "label": "Permit", "expires": on(-5)},
            {"id": "D-002", "label": "Insurance", "expires": on(20)},
            {"id": "D-003", "label": "Bond", "expires": on(400)},
            {"id": "D-004", "label": "COA", "expires": "n/a"},
        ]
        by = {d["id"]: d for d in calc.document_status(docs, TODAY)}
        self.assertEqual(by["D-001"]["state"], "expired")
        self.assertEqual(by["D-002"]["state"], "expiring")
        self.assertEqual(by["D-003"]["state"], "ok")
        self.assertEqual(by["D-004"]["state"], "unknown")

    def test_sorted_most_urgent_first(self):
        docs = [
            {"id": "ok", "label": "z", "expires": on(300)},
            {"id": "exp", "label": "a", "expires": on(-1)},
            {"id": "unk", "label": "m", "expires": "bad"},
            {"id": "soon", "label": "b", "expires": on(10)},
        ]
        ids = [d["id"] for d in calc.document_status(docs, TODAY)]
        self.assertEqual(ids, ["unk", "exp", "soon", "ok"])

    def test_needing_attention_drops_the_current_ones(self):
        docs = [
            {"id": "D-001", "label": "Permit", "expires": on(-5)},
            {"id": "D-003", "label": "Bond", "expires": on(400)},
        ]
        need = calc.documents_needing_attention(docs, TODAY)
        self.assertEqual([d["id"] for d in need], ["D-001"])

    def test_phrase_reads_in_plain_words(self):
        self.assertEqual(
            calc.doc_phrase({"state": "expired", "days": -1}),
            "expired 1 day ago")
        self.assertEqual(
            calc.doc_phrase({"state": "expiring", "days": 21}),
            "expires in 21 days")
        self.assertEqual(
            calc.doc_phrase({"state": "expiring", "days": 0}), "expires today")
        self.assertEqual(
            calc.doc_phrase({"state": "unknown", "days": None}),
            "no readable renewal date")

    def test_parse_date_rejects_gibberish(self):
        self.assertEqual(calc.parse_date("2027-03-01"), date(2027, 3, 1))
        with self.assertRaisesRegex(ValueError, "isn't a date"):
            calc.parse_date("March sometime")


class DocStoreTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-doc-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)

    def test_add_assigns_ids_and_keeps_only_given_fields(self):
        a = self.store.add_document("TTB Basic Permit", "2027-01-01",
                                    kind="permit", ref="BWN-CT-12345")
        b = self.store.add_document("Liability insurance", "2026-12-01")
        self.assertEqual(a["id"], "D-001")
        self.assertEqual(b["id"], "D-002")
        self.assertEqual(a["ref"], "BWN-CT-12345")
        self.assertNotIn("note", a)          # blanks are not stored
        self.assertNotIn("kind", b)
        self.assertEqual(len(self.store.list_documents()), 2)

    def test_add_requires_a_name_and_a_real_date(self):
        with self.assertRaisesRegex(ValueError, "give the document a name"):
            self.store.add_document("", "2027-01-01")
        with self.assertRaisesRegex(ValueError, "isn't a date"):
            self.store.add_document("Permit", "soon")

    def test_renew_moves_the_date_in_place(self):
        self.store.add_document("Permit", "2026-10-01")
        self.store.renew_document("D-001", "2027-10-01")
        self.assertEqual(self.store.list_documents()[0]["expires"],
                         "2027-10-01")
        self.assertEqual(len(self.store.list_documents()), 1)   # not appended
        with self.assertRaisesRegex(ValueError, "no document"):
            self.store.renew_document("D-099", "2027-10-01")


class DocPageTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-docpage-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)

    def get(self, path, params=None):
        return dispatch(Request("GET", path, params or {}, {}, (), self.store))

    def post(self, path, form):
        return dispatch(Request("POST", path, {}, form, (), self.store))

    def test_add_then_list_shows_status(self):
        r = self.post("/documents/add",
                      {"label": "CT Farm Winery Permit",
                       "expires": on(15), "kind": "permit"})
        self.assertEqual(r.status, 303)
        page = self.get("/documents").body
        self.assertIn("CT Farm Winery Permit", page)
        self.assertIn("expiring", page)          # 15 days out
        self.assertIn("need attention", page)    # the lede

    def test_renew_via_the_page(self):
        self.post("/documents/add", {"label": "Permit", "expires": on(-2)})
        page = self.get("/documents").body
        self.assertIn("expired", page)
        self.post("/documents/D-001/renew", {"expires": on(365)})
        page = self.get("/documents").body
        self.assertIn("current", page)
        self.assertIn("All 1 current", page)

    def test_today_raises_a_lapsing_permit(self):
        # an expiring permit shows on Today even with nothing fermenting
        self.post("/documents/add", {"label": "TTB Basic Permit",
                                     "expires": on(9)})
        home = self.get("/").body
        self.assertIn("Compliance", home)
        self.assertIn("TTB Basic Permit", home)
        self.assertIn("Nothing is fermenting", home)

    def test_today_is_quiet_when_everything_is_current(self):
        self.post("/documents/add", {"label": "Permit", "expires": on(400)})
        home = self.get("/").body
        self.assertNotIn("Compliance", home)


if __name__ == "__main__":
    unittest.main()
