"""Assign an ISO3 country code to each grid cell (Natural Earth, public domain).

Needs `shapely` (pip install shapely). The GeoJSON is downloaded once to data/.
"""
from __future__ import annotations

import json

import pandas as pd

from .config import DATA_DIR

NE_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
          "geojson/ne_50m_admin_0_countries.geojson")
NE_PATH = DATA_DIR / "ne_50m_admin_0_countries.geojson"


def _download():
    import requests

    resp = requests.get(NE_URL, timeout=120)
    resp.raise_for_status()
    NE_PATH.write_bytes(resp.content)


def assign_countries(cells: pd.DataFrame) -> pd.DataFrame:
    from shapely.geometry import Point, shape
    from shapely.strtree import STRtree

    if not NE_PATH.exists():
        _download()
    feats = json.loads(NE_PATH.read_text(encoding="utf-8"))["features"]
    geoms, codes = [], []
    for f in feats:
        p = f["properties"]
        code = p.get("ISO_A3") if p.get("ISO_A3") not in (None, "-99") else p.get("ADM0_A3")
        geoms.append(shape(f["geometry"]))
        codes.append(code)
    tree = STRtree(geoms)
    out = []
    for lon, lat in zip(cells["lon"], cells["lat"]):
        pt = Point(lon, lat)
        hit = None
        for i in tree.query(pt, predicate="intersects"):
            hit = codes[int(i)]
            break
        out.append(hit)
    cells = cells.copy()
    cells["iso3"] = out
    return cells
