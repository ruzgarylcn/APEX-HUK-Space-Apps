"""Export the Earth grid as one compact binary file (data/earth_grid.bin) so the static Atlas can
find discoveries for ANY target, custom points / areas / polygons included, with no API.

The browser runs the same pipeline as backend find_analogs(): score -> coverage >= 0.5 -> top 20 000
-> priority (income, novelty, access) -> 150 km regions -> quota selection. Target-independent parts
(nearest campaign, nearest catalog site, income group) are precomputed here.

Layout: uint32 header length, UTF-8 JSON header, zero padding to 4 bytes, then the arrays named in
header["arrays"] in order (little endian). Features are stored normalized to [0, 1] by the fixed
ranges of config/features.json as uint16 (0..65534; 65535 = missing).

    python tools/export_grid.py        (run from the repository root; needs pandas + pyarrow)
"""
import json
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from analog_atlas.config import features_config  # noqa: E402
from analog_atlas.features import normalize  # noqa: E402
from analog_atlas.pipeline import EARTH_FEATURES_PATH, add_novelty, load_campaigns, load_catalog  # noqa: E402
from analog_atlas.priority import load_income_groups  # noqa: E402

OUT = ROOT / "data" / "earth_grid.bin"


def main():
    import pandas as pd

    grid = pd.read_parquet(EARTH_FEATURES_PATH).reset_index(drop=True)
    n = len(grid)
    feats = [f for f in features_config()["features"] if not f.get("categorical")]
    keys = [f["key"] for f in feats]

    norm = normalize(grid)                                            # (n, k), NaN = missing
    q = np.where(np.isnan(norm), 65535, np.round(norm * 65534)).astype("<u2")

    iso_list = sorted({c for c in grid["iso3"] if isinstance(c, str)})
    iso_idx = np.array([iso_list.index(c) if isinstance(c, str) else 255 for c in grid["iso3"]], "<u1")
    lf_list = sorted({c for c in grid["landform_class"] if isinstance(c, str)})
    lf_idx = np.array([lf_list.index(c) if isinstance(c, str) else 255 for c in grid["landform_class"]], "<u1")

    camp, cat = load_campaigns(), load_catalog()
    nov = add_novelty(grid[["lat", "lon"]], campaigns=camp, catalog=cat)
    camp_names, cat_names = list(camp["name"]), list(cat["name"])
    camp_idx = np.array([camp_names.index(x) for x in nov["nearest_campaign"]], "<u1")
    cat_idx = np.array([cat_names.index(x) for x in nov["nearest_known_site"]], "<u1")

    income = dict(zip(*load_income_groups()[["iso3", "income"]].T.values))
    arrays = [
        ("lat", grid["lat"].to_numpy("<f4")),
        ("lon", grid["lon"].to_numpy("<f4")),
        ("access_minutes", grid["access_minutes"].to_numpy("<f4")),
        ("campaign_km", nov["campaign_km"].to_numpy("<f4")),
        ("known_site_km", nov["known_site_km"].to_numpy("<f4")),
        ("features", q.reshape(-1)),                                  # row-major (n, k)
        ("iso", iso_idx), ("landform", lf_idx), ("campaign", camp_idx), ("known_site", cat_idx),
    ]
    header = {
        "version": 1, "n": n, "keys": keys, "ranges": [f["range"] for f in feats],
        "iso3": iso_list, "income": {c: income.get(c, "NA") for c in iso_list}, "landforms": lf_list,
        "campaigns": camp_names, "known_sites": cat_names,
        "arrays": [[name, str(a.dtype.str), int(a.size)] for name, a in arrays],
        "source": "backend/data/earth_features.parquet (Google Earth Engine, ~50 km land grid)",
    }
    hb = json.dumps(header, separators=(",", ":")).encode("utf-8")
    pad = (-(4 + len(hb))) % 4
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("wb") as fh:
        fh.write(struct.pack("<I", len(hb) + pad))
        fh.write(hb + b" " * pad)
        for _, a in arrays:
            fh.write(np.ascontiguousarray(a).tobytes())
    print(f"wrote {OUT.relative_to(ROOT)}: {n} cells, {len(keys)} features, {OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
