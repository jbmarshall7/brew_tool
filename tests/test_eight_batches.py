"""Round 14: usable at eight batches.

Today holds what's in a tank; bottled batches get a short list while they
have bottles (or a conditioning check) left, and every batch ever made is on
/batches. A Feed-due card records the feed in one tap. A bottle-conditioned
mead is watched until a bottle is opened. Dates are relative to now.
"""
import re
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

NOW = datetime.now().replace(second=0, microsecond=0)


def ago(days=0, hours=0):
    return (NOW - timedelta(days=days, hours=hours)).strftime("%Y-%m-%dT%H:%M")


OWNER = {"gal": "6", "abv": "12", "og": "", "fg": "1.000", "yeast": "71B",
         "demand": "medium", "additions": "4", "name": "OB"}


class Case(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-eight-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)
        self.post("/recipes", OWNER)

    def get(self, path, params=None):
        return dispatch(Request("GET", path, params or {}, {}, (), self.store))

    def post(self, path, form):
        return dispatch(Request("POST", path, {}, form, (), self.store))

    def must(self, n, pitched):
        self.post("/recipes/ob/must",
                  {"gal": "6", "id": str(n), "pitched_at": pitched,
                   "volume_gal": "6", "og": "1.091", "cal_f": "60"})
        return f"B-{pitched[:4]}-{n:03d}"

    def finished(self, bid, days_ago=20):
        self.store.add_reading(bid, "1.000", at=ago(days_ago))
        self.store.add_reading(bid, "1.000", at=ago(days_ago - 3))

    def cellar(self, body):
        """The ids in the In-the-cellar table only."""
        if "In the cellar" not in body:
            return set()
        part = body.split("In the cellar")[1].split("</table>")[0]
        return set(re.findall(r'href="/batches/(B-\d{4}-\d{3})"', part))


class TodayAtScaleTest(Case):
    def test_bottled_batches_leave_the_cellar_table(self):
        working = self.must(1, ago(3))
        done = self.must(2, ago(40))
        self.finished(done)
        self.store.record_bottling(done, "28", "750 ml", at=ago(10))
        body = self.get("/").body
        self.assertEqual(self.cellar(body), {working})
        bottled = body.split("<h2>Bottled</h2>")[1]
        self.assertIn(done, bottled)
        self.assertIn(">28<", bottled)                   # on hand

    def test_a_sold_out_batch_lives_on_all_batches_only(self):
        done = self.must(1, ago(40))
        self.finished(done)
        self.store.record_bottling(done, "12", "750 ml", at=ago(10))
        self.store.record_disposition(done, "sold", "12", at=ago(5))
        self.assertNotIn(done, self.get("/").body.split("All batches")[0])
        self.assertIn(f'href="/batches/{done}"', self.get("/batches").body)


class FedButtonTest(Case):
    def test_the_feed_due_card_records_the_feed_and_comes_back(self):
        bid = self.must(1, ago(hours=25))                # feed #1 due
        body = self.get("/").body
        card = body.split("Needs you now")[1].split("In the cellar")[0]
        self.assertIn("Fed #1", card)
        once = re.search(r'name="once" value="([0-9a-f]+)"', card).group(1)
        r = self.post(f"/batches/{bid}/feed",
                      {"n": "1", "back": "today", "once": once})
        self.assertEqual(r.location.split("?")[0], "/")
        self.assertIn("Logged", unquote(r.location))
        self.assertEqual([f["n"] for f in self.store.load_batch(bid)["feeds"]],
                         [1])


class ConditioningTest(Case):
    def sparkling(self, capped_days_ago):
        bid = self.must(1, ago(60))
        self.finished(bid, days_ago=40)
        self.store.record_priming(bid, "2.5", "68", at=ago(capped_days_ago + 1))
        self.store.record_bottling(bid, "24", "750 ml", at=ago(capped_days_ago))
        return bid

    def act(self, bid):
        return calc.next_action(self.store.load_batch(bid), NOW)

    def test_capped_last_week_is_conditioning_not_done(self):
        a = self.act(self.sparkling(5))
        self.assertEqual(a["tag"], "Conditioning")
        self.assertIn("day 5", a["text"])

    def test_two_weeks_on_it_asks_for_a_test_bottle(self):
        bid = self.sparkling(16)
        a = self.act(bid)
        self.assertEqual((a["tag"], a["kind"]), ("Test a bottle", "warn"))
        self.assertIn("Gushing", a["text"])
        self.assertIn(bid, self.get("/").body.split("In the cellar")[0])

    def test_tasting_a_bottle_settles_it(self):
        bid = self.sparkling(16)
        self.store.record_tasting(bid, "in the bottle", 4, "lively, clean")
        self.assertEqual(self.act(bid)["tag"], "Bottled")

    def test_a_still_mead_is_simply_bottled(self):
        bid = self.must(1, ago(40))
        self.finished(bid)
        self.store.record_bottling(bid, "28", "750 ml", at=ago(2))
        self.assertEqual(self.act(bid)["tag"], "Bottled")


if __name__ == "__main__":
    unittest.main()
