"""The math the cellar depends on, pinned by hand-derived values.

Every expected value below was worked from the documented formula and the
constants in brew/calc.py, so a silent constant change or a rounding drift
fails loudly. Run from the repo root:  python3 -m unittest tests.test_calc
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew import calc as c


class GravityTest(unittest.TestCase):
    def test_abv(self):
        # (1.100 - 1.000) * 131.25 is 13.12500000000001 in binary, so
        # round() gives 13.13 (an exact 13.125 would round to 13.12)
        self.assertEqual(c.abv(1.100, 1.000), 13.13)
        self.assertEqual(c.abv(1.1067, 1.0), 14.0)

    def test_og_for_abv(self):
        # 1 + 14 / 131.25 = 1.10667 -> 1.1067
        self.assertEqual(c.og_for_abv(14), 1.1067)
        self.assertEqual(c.og_for_abv(12), 1.0914)

    def test_third_break(self):
        # 1.1067 - 0.1067/3 = 1.0711 -> 1.071
        self.assertEqual(c.third_break(1.1067), 1.071)
        self.assertEqual(c.third_break(1.1029), 1.069)

    def test_hydro_correct(self):
        # standard density polynomial, 60 F hydrometer
        self.assertEqual(c.hydro_correct(1.050, 77, 60), 1.052)
        self.assertEqual(c.hydro_correct(1.101, 76, 60), 1.1029)
        self.assertEqual(c.hydro_correct(1.101, 76, 68), 1.1021)
        self.assertEqual(c.hydro_correct(1.050, 60, 60), 1.05)


class HoneyWaterTest(unittest.TestCase):
    def test_honey_for_og(self):
        # 100 pts * 5 gal / 35 = 14.2857 -> 14.29
        self.assertEqual(c.honey_for_og(5, 1.100), 14.29)
        # 106.7 * 6 / 35 = 18.29 — the owner's real number, at 6 gal
        self.assertEqual(c.honey_for_og(6, 1.1067), 18.29)
        # ...and at the 5 gal the old recipe file claimed as its basis
        self.assertEqual(c.honey_for_og(5, 1.1067), 15.24)

    def test_honey_takes_room(self):
        # 18.29 lb / 12 lb per gal = 1.524 -> 1.52 gal
        self.assertEqual(c.honey_gal(18.29), 1.52)
        self.assertEqual(c.water_gal(6, 18.29), 4.48)

    def test_expected_og(self):
        # 1 + 18.3*35/6/1000 is 1.10674999... in binary (just under the
        # midpoint), so round() gives 1.1067; pages show 1.107 either way
        self.assertEqual(c.expected_og(18.3, 6), 1.1067)
        self.assertEqual(c.expected_og(15, 5), 1.105)


class YeastNutrientTest(unittest.TestCase):
    def test_yeast_and_goferm(self):
        self.assertEqual(c.yeast_grams(6), 6.0)
        self.assertEqual(c.sachets(10), 2.0)
        # 1.25 g Go-Ferm per g yeast; 20 mL water per g Go-Ferm
        self.assertEqual(c.goferm(10), (12.5, 250))
        self.assertEqual(c.goferm(6), (7.5, 150))

    def test_yan_medium(self):
        # 12.5 ppm per %ABV * 12 = 150 ppm; 150/40 * 5 gal = 18.75 -> 18.8 g
        self.assertEqual(c.yan_ppm(12, "medium"), 150)
        self.assertEqual(c.nutrient_grams(150, 5, "fermaid-o"), 18.8)
        self.assertEqual(c.split(150, 5, "fermaid-o", 3), 6.2)
        # the owner's batch: 175 ppm, 26.25 g -> 26.2 g as 4 x 6.6 g
        self.assertEqual(c.yan_ppm(14, "medium"), 175)
        self.assertEqual(c.nutrient_grams(175, 6, "fermaid-o"), 26.2)
        self.assertEqual(c.split(175, 6, "fermaid-o", 4), 6.6)

    def test_unknown_demand_or_product_refused(self):
        with self.assertRaises(ValueError):
            c.yan_ppm(12, "extreme")
        with self.assertRaises(ValueError):
            c.nutrient_grams(150, 5, "mystery-powder")

    def test_tolerance_note(self):
        self.assertIn("14 %", c.tolerance_note("71B", 14))
        self.assertIsNone(c.tolerance_note("71B", 12))
        self.assertIsNone(c.tolerance_note("EC-1118", 14))
        self.assertIn("past that", c.tolerance_note("lalvin 71b", 15))
        self.assertIn("fusels", c.tolerance_note("D47", 14))
        self.assertIsNone(c.tolerance_note("some house strain", 14))


class CorrectionTest(unittest.TestCase):
    def test_reads_low_add_honey(self):
        # 3.8 pts under; 3.8 * 6 / (35 - 106.7/12) = 0.873 -> 0.87 lb (14 oz)
        r = c.correction(1.1029, 1.1067, 6, strain="71B")
        self.assertEqual(r["add"], "honey")
        self.assertEqual(r["pts"], 3.8)
        self.assertEqual(r["lb"], 0.87)
        self.assertEqual(r["oz"], 14)
        self.assertEqual(r["adds_gal"], 0.07)
        self.assertEqual(r["carry_on_abv"], 13.5)
        self.assertFalse(r["over_tolerance"])

    def test_reads_high_add_water(self):
        # 5.3 pts over; 6 * (112/106.7 - 1) = 0.298 -> 0.30 gal (1.1 L)
        r = c.correction(1.112, 1.1067, 6, strain="71B")
        self.assertEqual(r["add"], "water")
        self.assertEqual(r["pts"], 5.3)
        self.assertEqual(r["gal"], 0.3)
        self.assertEqual(r["liters"], 1.1)
        self.assertEqual(r["new_gal"], 6.3)
        self.assertEqual(r["carry_on_abv"], 14.7)
        self.assertTrue(r["over_tolerance"])

    def test_within_resolution_is_on_target(self):
        self.assertEqual(c.correction(1.106, 1.1067, 6)["add"], "none")
        self.assertEqual(c.correction(1.1087, 1.1067, 6)["add"], "none")

    def test_ph(self):
        self.assertEqual(c.ph_verdict(3.9)["kind"], "ok")
        self.assertIn("happy", c.ph_verdict(3.9)["text"])
        self.assertEqual(c.ph_verdict(4.4)["kind"], "ok")
        self.assertIn("high side", c.ph_verdict(4.4)["text"])
        self.assertEqual(c.ph_verdict(3.6)["kind"], "ok")
        self.assertIn("low side, fine", c.ph_verdict(3.6)["text"])
        # 3.2-3.5 will likely crash in primary: a warning, not "fine"
        self.assertEqual(c.ph_verdict(3.25)["kind"], "warn")
        self.assertIn("drops further", c.ph_verdict(3.25)["text"])
        self.assertEqual(c.ph_verdict(3.1)["kind"], "warn")
        self.assertIn("floor", c.ph_verdict(3.1)["text"])
        # above 4.8 doubt the meter
        self.assertEqual(c.ph_verdict(7.0)["kind"], "warn")
        self.assertIn("calibration", c.ph_verdict(7.0)["text"])


class ScheduleTest(unittest.TestCase):
    def test_tosna_from_measured_og(self):
        s = c.schedule("2026-09-03T15:40", 1.1029, 1.0, 6, "medium",
                       "fermaid-o", 4)
        # 13.51 % -> 169 ppm -> 25.35 g -> 25.3 g total, 6.3 g each
        self.assertEqual(s["yan_ppm"], 169)
        self.assertEqual(s["total_g"], 25.3)
        self.assertEqual(s["stop_sg"], 1.069)
        rows = s["additions"]
        self.assertEqual(len(rows), 4)
        self.assertEqual([r["g"] for r in rows], [6.3] * 4)
        self.assertEqual([r["due"] for r in rows],
                         ["2026-09-04T15:40", "2026-09-05T15:40",
                          "2026-09-06T15:40", "2026-09-10T15:40"])
        self.assertTrue(all(r["stop_sg"] == 1.069 for r in rows))
        self.assertIn("1/3 break", rows[0]["rule"])
        self.assertIn("day 7", rows[3]["rule"])

    def test_other_counts(self):
        s3 = c.schedule("2026-09-03 08:00", 1.100, 1.0, 5, additions=3)
        self.assertEqual([r["due"][:10] for r in s3["additions"]],
                         ["2026-09-04", "2026-09-05", "2026-09-10"])
        s1 = c.schedule("2026-09-03", 1.100, 1.0, 5, additions=1)
        self.assertEqual(s1["additions"][0]["due"], "2026-09-04T00:00")

    def test_bad_when_refused(self):
        with self.assertRaises(ValueError):
            c.schedule("yesterday-ish", 1.100, 1.0, 5)

    def test_og_at_or_below_fg_refused(self):
        with self.assertRaisesRegex(ValueError, "leave anything"):
            c.schedule("2026-09-03T15:40", 0.998, 1.0, 5)
        with self.assertRaisesRegex(ValueError, "leave anything"):
            c.schedule("2026-09-03T15:40", 1.010, 1.010, 5)

    def test_finish_gravity_threads_through(self):
        # (1.1029 - 1.010) * 131.25 = 12.19 % -> 152 ppm -> 152/40*6 = 22.8 g
        s = c.schedule("2026-09-03T15:40", 1.1029, 1.010, 6)
        self.assertEqual((s["yan_ppm"], s["total_g"], s["stop_sg"]),
                         (152, 22.8, 1.072))


class PlanTest(unittest.TestCase):
    def test_the_owners_batch(self):
        p = c.plan(6, 14, yeast_g=10)
        self.assertEqual(p["strength_by"], "abv")
        self.assertEqual(p["og"], 1.1067)
        self.assertEqual(p["honey_lb"], 18.29)
        self.assertEqual(p["honey_lb_per_gal"], 3.05)
        self.assertEqual(p["honey_gal"], 1.52)
        self.assertEqual(p["water_gal"], 4.48)
        self.assertEqual(p["water_l"], 17.0)
        self.assertEqual(p["yeast_g"], 10.0)
        self.assertEqual(p["sachets"], 2.0)
        self.assertTrue(p["high_og_pitch"])
        self.assertEqual((p["goferm_g"], p["goferm_water_ml"]), (12.5, 250))
        self.assertEqual(p["yan_ppm"], 175)
        self.assertEqual(p["nutrient_g"], 26.2)
        self.assertEqual(p["per_addition_g"], 6.6)
        self.assertEqual(p["third_break_sg"], 1.071)
        self.assertEqual(p["abv_if_dry"], 14.0)
        self.assertEqual(len(p["warnings"]), 1)
        self.assertIn("71B", p["warnings"][0])

    def test_by_og_gives_the_same_sheet(self):
        by_abv = c.plan(6, 14, yeast_g=10)
        by_og = c.plan(6, og=1.1067, yeast_g=10)
        self.assertEqual(by_og["strength_by"], "og")
        for key in ("honey_lb", "water_gal", "yan_ppm", "nutrient_g",
                    "per_addition_g", "third_break_sg", "abv_if_dry"):
            self.assertEqual(by_og[key], by_abv[key], key)

    def test_finish_gravity_above_dry(self):
        # og = 1.010 + 14/131.25 = 1.1167; honey 116.7*6/35 = 20.01 lb;
        # third break 1.1167 - 0.1067/3 = 1.081
        p = c.plan(6, 14, fg=1.010, yeast_g=10)
        self.assertEqual((p["og"], p["honey_lb"], p["water_gal"],
                          p["third_break_sg"], p["abv_if_dry"], p["yan_ppm"]),
                         (1.1167, 20.01, 4.33, 1.081, 14.0, 175))
        q = c.plan(6, og=1.1067, fg=1.010)
        self.assertEqual((q["abv"], q["yan_ppm"], q["third_break_sg"]),
                         (12.69, 159, 1.074))

    def test_defaults(self):
        p = c.plan("6", "12")
        self.assertEqual(p["yeast_g"], 6.0)
        self.assertFalse(p["high_og_pitch"])
        self.assertEqual(p["warnings"], [])
        self.assertEqual(p["additions"], 4)

    def test_nonsense_refused_in_plain_words(self):
        with self.assertRaisesRegex(ValueError, "isn't a number"):
            c.plan("abc", 12)
        with self.assertRaisesRegex(ValueError, "target strength"):
            c.plan(6)
        with self.assertRaisesRegex(ValueError, "above 25"):
            c.plan(6, 40)
        with self.assertRaisesRegex(ValueError, "above 1.25"):
            c.plan(6, og=1.3)
        with self.assertRaisesRegex(ValueError, "below 0.1"):
            c.plan(0, 12)
        with self.assertRaisesRegex(ValueError, "leave anything"):
            c.plan(6, og=1.000)


class IdTest(unittest.TestCase):
    def test_next_batch_id(self):
        self.assertEqual(c.next_batch_id([], 2026), "B-2026-001")
        self.assertEqual(c.next_batch_id(["B-2026-003", "B-2025-009"], 2026),
                         "B-2026-004")
        self.assertEqual(c.next_batch_id(["B-2026-003"], 2027), "B-2027-001")


if __name__ == "__main__":
    unittest.main()
