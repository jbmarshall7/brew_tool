"""Vessels: a flat list, occupancy derived from the batches that name them.

A vessel is busy because a non-bottled batch holds it, free once bottled —
the page never invents a free-by date it cannot derive.
"""
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


def must(id_):
    return {"gal": "6", "id": id_, "pitched_at": "2026-08-10T15:40",
            "volume_gal": "6", "honey_lb": "18.3", "water_gal": "4.5",
            "yeast_g": "10", "goferm_g": "12.5", "og": "1.1067", "ph": "3.9"}


class VesselTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="brew-test-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.store = Store(self.root)
        dispatch(Request("POST", "/recipes", {}, OWNER, (), self.store))

    def post(self, path, form):
        return dispatch(Request("POST", path, {}, form, (), self.store))

    def get(self, path, params=None):
        return dispatch(Request("GET", path, params or {}, {}, (), self.store))

    def test_adding_vessels_and_ids(self):
        v = self.store.add_vessel("Carboy 1", "6")
        self.assertEqual(v["id"], "V-001")
        self.assertEqual(v["gal"], 6.0)
        self.assertEqual(self.store.add_vessel("Tank")["id"], "V-002")
        with self.assertRaisesRegex(ValueError, "already a vessel"):
            self.store.add_vessel("carboy 1")
        with self.assertRaisesRegex(ValueError, "give the vessel"):
            self.store.add_vessel("  ")

    def test_occupancy_is_derived_and_frees_on_bottling(self):
        self.store.add_vessel("Carboy 1")
        self.store.add_vessel("Carboy 2")
        dispatch(Request("POST", "/recipes/ob/must", {}, must("B-2026-003"), (),
                         self.store))
        self.store.set_batch_vessel("B-2026-003", "Carboy 1")
        occ = calc.vessel_occupancy(self.store.list_vessels(),
                                    self.store.list_batches(),
                                    datetime(2026, 9, 1, 10, 0))
        by_name = {o["vessel"]["name"]: o for o in occ}
        self.assertFalse(by_name["Carboy 1"]["free"])
        self.assertEqual(by_name["Carboy 1"]["batches"][0]["id"], "B-2026-003")
        self.assertTrue(by_name["Carboy 2"]["free"])
        # bottle it → the vessel frees
        self.store.add_reading("B-2026-003", "1.000", at="2026-08-28T09:00")
        self.store.record_bottling("B-2026-003", "28", "750 mL bottle")
        occ = calc.vessel_occupancy(self.store.list_vessels(),
                                    self.store.list_batches())
        self.assertTrue({o["vessel"]["name"]: o["free"]
                         for o in occ}["Carboy 1"])

    def test_the_vessels_page(self):
        self.store.add_vessel("Carboy 1", "6")
        dispatch(Request("POST", "/recipes/ob/must", {}, must("B-2026-003"), (),
                         self.store))
        self.store.set_batch_vessel("B-2026-003", "Carboy 1")
        body = self.get("/vessels").body
        self.assertIn("Carboy 1", body)
        self.assertIn("B-2026-003", body)
        self.assertIn("0 of 1 free", body)

    def test_the_add_route(self):
        r = self.post("/vessels/add", {"name": "Fermenter 2", "gal": "15"})
        self.assertEqual(r.status, 303)
        self.assertIn("Added%20Fermenter%202", r.location)
        self.assertEqual(len(self.store.list_vessels()), 1)

    def test_setting_a_batch_vessel_from_its_page(self):
        dispatch(Request("POST", "/recipes/ob/must", {}, must("B-2026-003"), (),
                         self.store))
        r = self.post("/batches/B-2026-003/vessel", {"vessel": "Carboy 3"})
        self.assertEqual(r.status, 303)
        self.assertEqual(self.store.load_batch("B-2026-003")["vessel"],
                         "Carboy 3")

    def test_empty_cellar_of_vessels(self):
        self.assertIn("No vessels yet", self.get("/vessels").body)


if __name__ == "__main__":
    unittest.main()
