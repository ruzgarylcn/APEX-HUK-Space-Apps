"""Similarity engine (vectorized port of the frontend Web Worker, metric v2).

    delta_k = norm(target_k) - norm(candidate_k)      (fixed physical ranges)
    d       = sqrt( sum w_k * delta_k^2 / sum w_k )   (over features present for that row)
    SI      = 100 * (1 - d)

Landform contributes delta = 1 - affinity. Works on 12 catalog sites or millions of
grid cells alike: everything is a numpy array operation, no Python loop over rows.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import family_ids, features_config, numeric_features
from .features import ensure_columns, normalize


def feature_weights(profile: str | None = None, custom: dict | None = None) -> dict[str, float]:
    """Per-feature weights: each family weight is split evenly across its member features."""
    cfg = features_config()
    if custom:
        total = sum(max(0.0, float(custom.get(f, 0))) for f in family_ids())
        fam = {f: (max(0.0, float(custom.get(f, 0))) / total if total > 0 else 1 / len(family_ids()))
               for f in family_ids()}
    else:
        fam = cfg["profiles"][profile or "landing"]["families"]
    weights = {}
    for fid in family_ids():
        members = [f["key"] for f in cfg["features"] if f["family"] == fid]
        for key in members:
            weights[key] = fam.get(fid, 0.0) / len(members)
    return weights


def _affinity(target_class: str | None, classes: pd.Series) -> np.ndarray:
    table = features_config()["landform_affinity"]

    def aff(c):
        if c is None or (isinstance(c, float) and np.isnan(c)) or target_class is None:
            return np.nan
        if c == target_class:
            return 1.0
        return table.get(f"{target_class}|{c}", table.get(f"{c}|{target_class}", 0.0))

    return classes.map(aff).to_numpy(dtype=float)


def score(target: dict, candidates: pd.DataFrame, *, profile: str = "landing",
          custom_weights: dict | None = None) -> pd.DataFrame:
    """Score every candidate row against one target feature dict.

    Returns a copy of `candidates` with `si`, one `fam_<family>` column per family and
    `coverage` (share of the profile's weight that had data for that row).
    """
    cfg = features_config()
    cand = ensure_columns(candidates.copy())
    num = numeric_features()
    keys = [f["key"] for f in num]
    w_all = feature_weights(profile, custom_weights)
    w = np.array([w_all[k] for k in keys])
    w_land = w_all.get("landform_class", 0.0)

    tvec = normalize(pd.DataFrame([target]))[0]                 # (k,)
    cmat = normalize(cand)                                      # (n, k)
    delta = tvec[None, :] - cmat                                # (n, k), NaN where missing
    present = ~np.isnan(delta)
    d2 = np.where(present, delta ** 2, 0.0)

    aff = _affinity(target.get("landform_class"), cand["landform_class"])
    land_present = ~np.isnan(aff)
    land_d2 = np.where(land_present, (1 - np.nan_to_num(aff)) ** 2, 0.0)

    num_w = (d2 * w).sum(axis=1) + w_land * land_d2
    den_w = (present * w).sum(axis=1) + w_land * land_present
    total_w = w.sum() + w_land
    with np.errstate(invalid="ignore", divide="ignore"):
        dist = np.sqrt(num_w / den_w)
    cand["si"] = np.where(den_w > 0, np.clip(100 * (1 - dist), 0, 100), np.nan)
    cand["coverage"] = den_w / total_w if total_w > 0 else 0.0

    for fid in family_ids():
        if fid == "landform":
            cand["fam_landform"] = aff * 100
            continue
        idx = [i for i, f in enumerate(num) if f["family"] == fid]
        sub, ok = d2[:, idx], present[:, idx]
        cnt = ok.sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            cand[f"fam_{fid}"] = np.where(cnt > 0, np.clip(100 * (1 - np.sqrt(sub.sum(axis=1) / cnt)), 0, 100), np.nan)

    cand.attrs["delta"] = delta          # kept for explain(); not serialized
    cand.attrs["keys"] = keys
    cand.attrs["gap_threshold"] = cfg["gap_threshold"]
    return cand


def explain(scored: pd.DataFrame, positions, target: dict, top_families: int = 2, max_gaps: int = 3) -> list[dict]:
    """'What is similar / where it breaks' for selected row positions (cheap: only top-N rows)."""
    delta, keys, thr = scored.attrs["delta"], scored.attrs["keys"], scored.attrs["gap_threshold"]
    fam_cols = [f"fam_{f}" for f in family_ids()]
    out = []
    for pos in positions:
        row = scored.iloc[pos]
        fams = sorted(((c[4:], row[c]) for c in fam_cols if pd.notna(row[c])), key=lambda x: -x[1])
        d = delta[pos]
        gap_idx = [i for i in np.argsort(-np.abs(np.nan_to_num(d))) if np.isfinite(d[i]) and abs(d[i]) >= thr][:max_gaps]
        out.append({
            "strongest": [{"family": f, "score": round(float(v), 1)} for f, v in fams[:top_families]],
            "breaks_on": [{"feature": keys[i], "target": target.get(keys[i]), "candidate": row[keys[i]],
                           "normalized_delta": round(float(d[i]), 3)} for i in gap_idx],
        })
    return out
