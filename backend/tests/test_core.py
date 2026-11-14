"""Core behaviour tests.   python -m unittest discover -s tests -v"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analog_atlas.config import numeric_keys  # noqa: E402
from analog_atlas.extract.earth_gee import postprocess  # noqa: E402
from analog_atlas.features import noon_sun_elevation  # noqa: E402
from analog_atlas.grid import build_grid  # noqa: E402
from analog_atlas.pipeline import get_target, load_catalog, rank  # noqa: E402
from analog_atlas.priority import apply_priority  # noqa: E402
from analog_atlas.scoring import score  # noqa: E402

INCOME = pd.DataFrame({"iso3": ["AAA", "BBB", "CCC"], "income": ["HIC", "LMC", "LIC"]})


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        _, self.cerberus = get_target("cerberus")

    def test_identical_vector_scores_100(self):
        cand = pd.DataFrame([self.cerberus])
        self.assertAlmostEqual(score(self.cerberus, cand)["si"].iloc[0], 100.0, places=6)

    def test_scores_do_not_depend_on_other_candidates(self):
        """Fixed physical ranges: adding a site must not change anyone else's SI."""
        base = score(self.cerberus, self.catalog)["si"].to_numpy()
        extra = pd.concat([self.catalog, pd.DataFrame([self.cerberus])], ignore_index=True)
        again = score(self.cerberus, extra)["si"].to_numpy()[: len(base)]
        np.testing.assert_allclose(base, again)

    def test_missing_features_reduce_coverage_not_crash(self):
        cand = self.catalog.head(1).copy()
        cand["mineral_olivine"] = np.nan
        cand["cave_index"] = np.nan
        out = score(self.cerberus, cand, profile="science")
        self.assertLess(out["coverage"].iloc[0], 1.0)
        self.assertTrue(0 <= out["si"].iloc[0] <= 100)

    def test_known_analog_is_near_the_top(self):
        """Sanity check against literature: McCartys is the type analog for Cerberus Palus."""
        si = score(self.cerberus, self.catalog, profile="landing").sort_values("si", ascending=False)
        self.assertIn("mccartys", list(si["id"].head(6)))

    def test_all_numeric_features_present(self):
        out = score(self.cerberus, self.catalog)
        for key in numeric_keys():
            self.assertIn(key, out.columns)


class PriorityTests(unittest.TestCase):
    def frame(self, si_values, codes):
        return pd.DataFrame({"si": si_values, "iso3": codes})

    def test_priority_never_filters(self):
        out = apply_priority(self.frame([90, 80, 70], ["AAA", "BBB", "CCC"]), income=INCOME)
        self.assertEqual(len(out), 3)

    def test_bonus_reorders_close_scores(self):
        out = apply_priority(self.frame([80, 76], ["AAA", "BBB"]), income=INCOME)
        self.assertEqual(list(out["iso3"]), ["BBB", "AAA"])          # 76 + 7 > 80

    def test_bonus_cannot_overturn_a_clearly_better_analog(self):
        out = apply_priority(self.frame([90, 76], ["AAA", "BBB"]), income=INCOME)
        self.assertEqual(list(out["iso3"]), ["AAA", "BBB"])          # 76 + 7 < 90

    def test_weak_analogs_get_no_bonus(self):
        out = apply_priority(self.frame([55], ["CCC"]), income=INCOME)
        self.assertEqual(out["income_bonus"].iloc[0], 0)
        self.assertEqual(out["opportunity"].iloc[0], 55)

    def test_si_is_reported_unchanged(self):
        out = apply_priority(self.frame([76], ["BBB"]), income=INCOME)
        self.assertEqual(out["si"].iloc[0], 76)


class GeometryAndExtractionTests(unittest.TestCase):
    def test_sun_elevation(self):
        self.assertAlmostEqual(float(noon_sun_elevation("earth", 0.0)), 90 - 23.44 * 2 / np.pi, delta=0.3)
        self.assertLess(float(noon_sun_elevation("moon", -89.9)), 2.0)

    def test_grid_cells_are_near_equal_area(self):
        g = build_grid(50, (20, 30, 30, 60))
        widths_km = g["half_dlon"] * 2 * 111.32 * np.cos(np.radians(g["lat"]))
        self.assertLess(widths_km.std() / widths_km.mean(), 0.05)

    def test_postprocess_outputs_every_feature(self):
        raw = pd.DataFrame({
            "cell_id": ["a"], "lat": [38.5], "lon": [28.6], "raw_slope": [6.0], "raw_slope_sq": [52.0],
            "raw_tri": [9.0], "raw_relief_5km": [180.0], "raw_albedo": [0.13], "raw_ati": [0.03],
            "raw_temp_min": [-6.0], "raw_diurnal_range": [24.0], "raw_frost_fraction": [0.12],
            "raw_mean_lst": [16.0], "raw_precip_mm": [550.0], "raw_pet_mm": [1300.0],
            "raw_mafic_index": [1.02], "raw_carbonate_index": [1.005], "raw_fe_ratio": [1.4], "raw_clay_ratio": [1.1],
            "raw_dust_aod": [0.05], "raw_ndvi": [0.3],
        })
        f = postprocess(raw)
        for key in numeric_keys():
            self.assertIn(key, f.columns)
        self.assertAlmostEqual(f["slope_std"].iloc[0], 4.0)


class ValidationTests(unittest.TestCase):
    def test_every_anchor_exists_and_is_ranked(self):
        from analog_atlas.pipeline import validate

        detail = validate(["landing"])
        self.assertEqual(set(detail["target"]), {"jezero", "cerberus", "gale", "shackleton", "marius"})
        self.assertTrue((detail["rank"] >= 1).all() and (detail["rank"] <= detail["of"]).all())


class DiscoveryChecklistTests(unittest.TestCase):
    def test_planted_match_passes_and_random_baseline_is_reported(self):
        from analog_atlas.config import numeric_features
        from analog_atlas.pipeline import check_discoveries

        rng = np.random.default_rng(1)
        grid = build_grid(300)                         # coarse synthetic global grid
        for f in numeric_features():
            grid[f["key"]] = rng.uniform(*f["range"], len(grid))
        grid["landform_class"] = "lava_flow"
        # Plant an exact copy of the Tharsis target at Emi Koussi (19.79N, 18.55E).
        _, tharsis = get_target("tharsis")
        i = int(((grid["lat"] - 19.79) ** 2 + (grid["lon"] - 18.55) ** 2).idxmin())
        for k, v in tharsis.items():
            grid.loc[i, k] = v
        grid.loc[i, ["lat", "lon"]] = [19.79, 18.55]   # coarse cell centre may be > radius away
        detail, summary = check_discoveries(grid, profiles=["science"], n_random=20)
        ek = detail[detail["candidate"] == "emi_koussi"].iloc[0]
        self.assertTrue(ek["pass"] and ek["strong_pass"])
        self.assertAlmostEqual(ek["best_si"], 100.0, places=1)
        self.assertIn("random_pass_rate", summary.columns)
        self.assertEqual(len(detail), 10)


class PipelineTests(unittest.TestCase):
    def test_rank_returns_explanations(self):
        _, gale = get_target("gale")
        head = rank(gale, load_catalog(), profile="science", top=5)
        self.assertEqual(len(head), 5)
        first = head["explanation"].iloc[0]
        self.assertEqual(len(first["strongest"]), 2)
        self.assertTrue(all("feature" in b for b in first["breaks_on"]))


if __name__ == "__main__":
    unittest.main()
