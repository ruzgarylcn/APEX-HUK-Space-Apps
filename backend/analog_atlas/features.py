"""Feature-vector assembly (v2, body-agnostic).

The same 22 numeric features + landform class describe an Earth grid cell, a catalog
site and a Moon/Mars target, so they can be compared directly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import features_config, numeric_keys

MINERALS = ["olivine", "pyroxene", "plagioclase", "evaporite", "hematite", "phyllosilicate", "carbonate"]


def noon_sun_elevation(body: str, lat: float | np.ndarray, samples: int = 72) -> np.ndarray:
    """Annual-mean noon solar elevation (deg, >= 0) for a latitude on a body.

    Averages 90 - |lat - decl| over a sinusoidal declination cycle decl = eps * sin(t).
    Matches noonSunElevation() in the frontend.
    """
    eps = features_config()["obliquity_deg"][body]
    lat = np.asarray(lat, dtype=float)
    t = 2 * np.pi * np.arange(samples) / samples
    dec = eps * np.sin(t)
    elev = np.clip(90 - np.abs(lat[..., None] - dec), 0, None)
    return elev.mean(axis=-1)


def assemble(*, body: str, lat: float, slope_mean: float, slope_std: float, roughness: float,
             albedo: float, temp_min: float, mineralogy: dict, analog: dict, landform: str) -> dict:
    """One feature dict in the canonical v2 layout."""
    a, m = analog or {}, mineralogy or {}
    row = {
        "slope_mean": slope_mean, "slope_std": slope_std, "roughness": roughness,
        "relief_local": a.get("relief_local", 0.0), "crater_density": a.get("crater_density", 0.0),
        "albedo": albedo, "ti_rel": a.get("ti_rel", 0.5), "rock_abundance": a.get("rock_abundance", 0.0),
        "temp_min": temp_min, "diurnal_range": a.get("diurnal_range", 0.0),
        "frost_fraction": a.get("frost_fraction", 0.0),
        "sun_elev_noon": float(noon_sun_elevation(body, lat)),
        "aridity": a.get("aridity", 0.0), "ground_ice": a.get("ground_ice", 0.0),
        "dust_activity": a.get("dust_activity", 0.0), "vegetation_cover": a.get("vegetation_cover", 0.0),
        "cave_index": a.get("cave_index", 0.0),
        "landform_class": landform,
    }
    for name in MINERALS:
        row[f"mineral_{name}"] = m.get(name, 0.0)
    return row


def from_catalog_site(site: dict) -> dict:
    """Feature dict for a literature catalog site (backend/data/catalog_sites.json)."""
    return assemble(body="earth", lat=site["lat"], slope_mean=site["terrain"]["slope_mean"],
                    slope_std=site["terrain"]["slope_std"], roughness=site["terrain"]["roughness"],
                    albedo=site["thermal"]["albedo"], temp_min=site["climate"]["temp_min"],
                    mineralogy=site["mineralogy"], analog=site["analog"], landform=site["landform_class"])


def from_target(target: dict) -> dict:
    """Feature dict for a Moon/Mars target (backend/config/targets.json)."""
    t = target["terrain"]
    return assemble(body=target["planet"], lat=target["lat"], slope_mean=t["slope_mean"],
                    slope_std=t["slope_std"], roughness=t["roughness"], albedo=target["albedo"],
                    temp_min=target["temp_min"], mineralogy=target["mineralogy"],
                    analog=target["analog"], landform=target["landform_class"])


def normalize(frame: pd.DataFrame) -> np.ndarray:
    """(n, k) matrix of features scaled to [0, 1] by their FIXED physical ranges.

    Missing values stay NaN; the scorer drops them from both numerator and weight sum,
    so a grid cell with no ASTER coverage is judged on the features it does have.
    """
    cols = []
    for f in features_config()["features"]:
        if f.get("categorical"):
            continue
        lo, hi = f["range"]
        v = pd.to_numeric(frame[f["key"]], errors="coerce").to_numpy(dtype=float)
        cols.append(np.clip((v - lo) / (hi - lo), 0.0, 1.0))
    return np.column_stack(cols)


def ensure_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Add any missing feature column as NaN (landform as None) so partial grids still score."""
    for key in numeric_keys():
        if key not in frame.columns:
            frame[key] = np.nan
    if "landform_class" not in frame.columns:
        frame["landform_class"] = None
    return frame
