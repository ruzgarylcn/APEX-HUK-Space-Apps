"""Anchor & Discover, clustering, novelty, access, quota and merge-exports tests."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analog_atlas import pipeline  # noqa: E402
from analog_atlas.config import numeric_features, priority_config  # noqa: E402
from analog_atlas.extract.earth_gee import RAW_BANDS, merge_exports  # noqa: E402
from analog_atlas.grid import build_grid  # noqa: E402
from analog_atlas.priority import access_bonus, apply_priority, select  # noqa: E402

INCOME = pd.DataFrame({"iso3": ["HHH", "LLL", "MMM"], "income": ["HIC", "LIC", "LMC"]})


class ClusteringTests(unittest.TestCase):
    def test_nearby_cells_collapse_into_one_region(self):
        df = pd.DataFrame({"lat": [10.0, 10.3, 10.6, 30.0], "lon": [20.0, 20.2, 20.1, 40.0], "si": [90, 88, 85, 80]})
        regions = pipeline.cluster_regions(df, radius_km=150)
        self.assertEqual(len(regions), 2)
        self.assertEqual(int(regions["region_cells"].iloc[0]), 3)
        self.assertAlmostEqual(regions["region_mean_si"].iloc[0], round((90 + 88 + 85) / 3, 1))

    def test_region_keeps_its_best_cell(self):
        df = pd.DataFrame({"lat": [0.0, 0.5], "lon": [0.0, 0.5], "si": [70, 95]}).sort_values("si", ascending=False)
        self.assertEqual(pipeline.cluster_regions(df)["si"].iloc[0], 95)


class NoveltyTests(unittest.TestCase):
    def test_known_nearby_and_novelty_scale(self):
        camp = pd.DataFrame({"name": ["X"], "lat": [0.0], "lon": [0.0]})
        cat = pd.DataFrame({"name": ["S"], "lat": [50.0], "lon": [50.0]})
        c = pd.DataFrame({"lat": [0.1, 0.0, 0.0, 50.2], "lon": [0.1, 2.25, 10.0, 50.0]})
        out = pipeline.add_novelty(c, campaigns=camp, catalog=cat)
        self.assertTrue(out["known_nearby"].iloc[0])            # ~16 km from a campaign
        self.assertAlmostEqual(out["novelty"].iloc[1], 250 / 500, delta=0.01)
        self.assertEqual(out["novelty"].iloc[2], 1.0)           # > 500 km: fully novel
        self.assertTrue(out["known_nearby"].iloc[3])            # near a catalog site, far from campaigns

    def test_novelty_bonus_capped_and_needs_si60(self):
        f = pd.DataFrame({"si": [80, 59], "iso3": ["HHH", "HHH"], "novelty": [1.0, 1.0]})
        out = apply_priority(f, income=INCOME, novelty_col="novelty").sort_values("si")
        self.assertEqual(out["novelty_bonus"].tolist(), [0.0, priority_config()["novelty"]["max_bonus"]])


class AccessTests(unittest.TestCase):
    def test_access_bonus_bounds(self):
        a = priority_config()["access"]
        b = access_bonus([0, a["full_bonus_minutes"], a["zero_bonus_minutes"], 10 ** 6, np.nan])
        self.assertEqual(b[0], a["max_bonus"])
        self.assertEqual(b[1], a["max_bonus"])
        self.assertEqual(b[2], 0.0)
        self.assertEqual(b[3], 0.0)
        self.assertEqual(b[4], 0.0)

    def test_hard_access_is_flagged_not_removed(self):
        f = pd.DataFrame({"si": [80, 80], "iso3": ["HHH", "HHH"], "access_minutes": [30, 5000]})
        out = apply_priority(f, income=INCOME)
        self.assertEqual(len(out), 2)
        self.assertEqual(int(out["hard_access"].sum()), 1)

    def test_all_bonuses_together_cannot_overturn_a_clearly_better_analog(self):
        cap = 10 + priority_config()["novelty"]["max_bonus"] + priority_config()["access"]["max_bonus"]
        f = pd.DataFrame({"si": [70 + cap + 1, 70], "iso3": ["HHH", "LLL"], "novelty": [0, 1], "access_minutes": [9999, 0]})
        out = apply_priority(f, income=INCOME, novelty_col="novelty")
        self.assertEqual(out["iso3"].iloc[0], "HHH")


class SelectionTests(unittest.TestCase):
    def _regions(self):
        # 30 HIC regions with the best SI, 30 LIC regions slightly lower.
        si = np.r_[np.linspace(95, 80, 30), np.linspace(79, 70, 30)]
        iso = ["HHH"] * 30 + ["LLL"] * 30
        return apply_priority(pd.DataFrame({"si": si, "iso3": iso}), income=INCOME)

    def test_quota_reserves_half_for_global_south_and_rest_by_pure_si(self):
        cfg = {**priority_config(), "selection": {"mode": "quota", "quota": {"top_n": 20, "min_global_south": 10,
                                                                             "global_south_groups": ["LIC", "LMC", "UMC"]}}}
        self.assertEqual(cfg["min_si_for_bonus"], 60)
        out = select(self._regions(), 20, cfg)
        self.assertEqual(len(out), 20)
        self.assertEqual(int((out["income_group"] == "LIC").sum()), 10)
        hic = out[out["income_group"] == "HIC"]["si"]
        self.assertAlmostEqual(hic.max(), 95.0)                # the best physics is never pushed out

    def test_bonus_mode_is_plain_opportunity_order(self):
        cfg = {**priority_config(), "selection": {"mode": "bonus"}}
        regions = self._regions()
        out = select(regions, 5, cfg)
        self.assertEqual(list(out.index), list(regions.index[:5]))


class MergeExportsTests(unittest.TestCase):
    def test_merge_joins_grid_and_dedupes(self):
        grid = build_grid(500, (20, 30, 40, 50))
        grid["iso3"] = "TUR"
        rows = [{"cell_id": c, **{b: 1.0 for b in RAW_BANDS}, "raw_slope": 5.0, "raw_slope_sq": 34.0,
                 "raw_access_minutes": 90.0} for c in grid["cell_id"]]
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a.csv", Path(d) / "b.csv"
            pd.DataFrame(rows[:3]).assign(**{"system:index": 0, ".geo": "x"}).to_csv(a, index=False)
            pd.DataFrame(rows[2:]).to_csv(b, index=False)                        # one duplicated cell
            out = merge_exports([a, b], grid)
        self.assertEqual(len(out), len(grid))
        self.assertTrue((out["iso3"] == "TUR").all())
        self.assertAlmostEqual(out["slope_std"].iloc[0], 3.0)
        self.assertTrue((out["access_minutes"] == 90.0).all())
        for f in numeric_features():
            self.assertIn(f["key"], out.columns)


class FindAnalogsTests(unittest.TestCase):
    def test_cerberus_returns_mccartys_anchor_and_reasoned_discoveries(self):
        rng = np.random.default_rng(3)
        g = build_grid(200)
        for f in numeric_features():
            g[f["key"]] = rng.uniform(*f["range"], len(g))
        g["landform_class"] = "lava_flow"
        g["iso3"] = np.where(g["lon"] > 0, "LLL", "HHH")
        g["access_minutes"] = 600.0
        _, cer = pipeline.get_target("cerberus")
        i = int(((g["lat"] - 12.0) ** 2 + (g["lon"] - 20.0) ** 2).idxmin())
        for k, v in cer.items():
            g.loc[i, k] = v
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "earth_features.parquet"
            g.to_parquet(path, index=False)
            with mock.patch.object(pipeline, "EARTH_FEATURES_PATH", path), \
                 mock.patch("analog_atlas.priority.load_income_groups", return_value=INCOME):
                r = pipeline.find_analogs("cerberus", profile="landing", top=10)
        names = [a["id"] for a in r["anchors"] if a["is_anchor"]]
        self.assertIn("mccartys", names)
        self.assertEqual(r["discovery_source"], "grid")
        self.assertGreater(len(r["discoveries"]), 0)
        best = max(r["discoveries"], key=lambda x: x["si"])
        self.assertAlmostEqual(best["si"], 100.0, places=1)
        for d_ in r["discoveries"]:
            for key in ("explanation", "income_group", "novelty", "access_minutes", "known_nearby", "region_cells", "slot"):
                self.assertIn(key, d_)
            self.assertEqual(len(d_["explanation"]["strongest"]), 2)


class ExportOfflineTests(unittest.TestCase):
    def test_export_offline_embeds_every_preset_and_profile(self):
        import argparse
        import json
        import re

        from analog_atlas import cli
        from analog_atlas.config import features_config, targets

        rng = np.random.default_rng(5)
        g = build_grid(400)
        for f in numeric_features():
            g[f["key"]] = rng.uniform(*f["range"], len(g))
        g["landform_class"] = "lava_flow"
        g["iso3"] = "LLL"
        with tempfile.TemporaryDirectory() as d:
            path, html = Path(d) / "earth_features.parquet", Path(d) / "index.html"
            g.to_parquet(path, index=False)
            html.write_text('<script type="application/json" id="offline-results">\n{}\n</script>', encoding="utf-8")
            with mock.patch.object(pipeline, "EARTH_FEATURES_PATH", path), \
                 mock.patch("analog_atlas.priority.load_income_groups", return_value=INCOME), \
                 mock.patch.object(cli, "OUT_DIR", Path(d) / "out"):
                import contextlib
                import io
                with contextlib.redirect_stdout(io.StringIO()):
                    cli.cmd_export_offline(argparse.Namespace(top=3, embed=str(html)))
            data = json.loads(re.search(r'id="offline-results">(.*?)</script>', html.read_text(encoding="utf-8"), re.S).group(1))
        self.assertEqual(len(data), len(targets()) * len(features_config()["profiles"]))
        self.assertTrue(all(v["source"] == "grid" and v["discoveries"] for v in data.values()))


class ApiTests(unittest.TestCase):
    def test_find_analogs_endpoint(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:  # pragma: no cover
            self.skipTest("fastapi/httpx not installed")
        from analog_atlas.api import app

        c = TestClient(app)
        r = c.post("/find-analogs", json={"target_id": "jezero", "profile": "science"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("salda", [a["id"] for a in body["anchors"] if a["is_anchor"]])
        self.assertEqual(body["discovery_source"], "none")
        self.assertEqual(c.post("/find-analogs", json={"target_id": "nope"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
