"""High-level operations shared by the CLI and the API."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .config import DATA_DIR, family_ids, targets
from .features import from_catalog_site, from_target
from .priority import apply_priority
from .scoring import explain, score

CATALOG_PATH = DATA_DIR / "catalog_sites.json"
EARTH_FEATURES_PATH = DATA_DIR / "earth_features.parquet"


def load_catalog() -> pd.DataFrame:
    sites = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    rows = []
    for s in sites:
        r = from_catalog_site(s)
        r.update({"id": s["id"], "name": s["name"], "country": s["country"], "iso3": s["iso3"],
                  "lat": s["lat"], "lon": s["lon"], "known_analog": True})
        rows.append(r)
    return pd.DataFrame(rows)


def load_candidates(source: str = "auto") -> tuple[pd.DataFrame, str]:
    """Earth grid features if extracted, else the 12-site literature catalog."""
    if source in ("auto", "grid") and EARTH_FEATURES_PATH.exists():
        return pd.read_parquet(EARTH_FEATURES_PATH), "grid"
    if source == "grid":
        raise FileNotFoundError(f"{EARTH_FEATURES_PATH} not found - run the extraction first")
    return load_catalog(), "catalog"


def get_target(target_id: str) -> tuple[dict, dict]:
    for t in targets():
        if t["id"] == target_id:
            return t, from_target(t)
    raise KeyError(f"unknown target '{target_id}' (see config/targets.json)")


def rank(target_features: dict, candidates: pd.DataFrame, *, profile: str = "landing",
         custom_weights: dict | None = None, top: int = 20, min_coverage: float = 0.5) -> pd.DataFrame:
    """Score, apply the Global South priority, keep the top rows and attach explanations."""
    # Positional index so explain() can address rows of the full scored frame by label.
    scored = score(target_features, candidates.reset_index(drop=True), profile=profile,
                   custom_weights=custom_weights)
    # Cells with too little data (e.g. ASTER gaps) are not ranked rather than ranked on scraps.
    prioritized = apply_priority(scored[scored["coverage"] >= min_coverage])
    head = prioritized.head(top).copy()
    head["explanation"] = explain(scored, list(head.index), target_features)
    return head


def validate(profiles: list[str] | None = None) -> pd.DataFrame:
    """Rank of each literature anchor (config/anchors.json) among catalog sites, by pure SI.

    Uses SI, not opportunity: validation tests the physics, not the priority policy.
    """
    from .config import CONFIG_DIR, features_config

    anchors = json.loads((CONFIG_DIR / "anchors.json").read_text(encoding="utf-8"))["anchors"]
    profiles = profiles or list(features_config()["profiles"])
    catalog = load_catalog()
    n = len(catalog)
    rows = []
    for tid, expected in anchors.items():
        _, feats = get_target(tid)
        for prof in profiles:
            ranked = score(feats, catalog, profile=prof).sort_values("si", ascending=False).reset_index(drop=True)
            for e in expected:
                pos = int(ranked.index[ranked["id"] == e["site"]][0]) + 1
                rows.append({"target": tid, "profile": prof, "anchor": e["site"], "rank": pos, "of": n,
                             "si": round(float(ranked.loc[pos - 1, "si"]), 1),
                             "top_site": ranked.loc[0, "id"], "cite": ",".join(e["cite"])})
    return pd.DataFrame(rows)


def validation_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Per profile: best anchor rank per target -> hit@1/3/5, MRR, and the random baseline."""
    best = frame.groupby(["profile", "target"])["rank"].min().reset_index()
    n = int(frame["of"].iloc[0])
    out = best.groupby("profile")["rank"].agg(
        targets="count",
        hit1=lambda r: (r <= 1).mean(), hit3=lambda r: (r <= 3).mean(), hit5=lambda r: (r <= 5).mean(),
        mrr=lambda r: (1 / r).mean())
    # Random baseline for hit@5 with k anchors among n sites ~ 1 - C(n-k,5)/C(n,5); report single-anchor case.
    out["random_hit5"] = 5 / n
    return out.round(3)


def _haversine_km(lat0: float, lon0: float, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    p = np.radians
    a = np.sin(p(lat - lat0) / 2) ** 2 + np.cos(p(lat0)) * np.cos(p(lat)) * np.sin(p(lon - lon0) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def check_discoveries(grid: pd.DataFrame | None = None, profiles: list[str] | None = None,
                      n_random: int = 100, seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Frozen discovery checklist (config/discovery_checklist.json) against the global grid.

    For each candidate and profile: best pure-SI cell within radius_km, as a percentile of all
    scored land cells. A random-point baseline with the same radii gives the chance pass rate.
    Returns (detail, summary).
    """
    from .config import CONFIG_DIR

    cfg = json.loads((CONFIG_DIR / "discovery_checklist.json").read_text(encoding="utf-8"))
    proto = cfg["protocol"]
    profiles = profiles or [proto["primary_profile"], *proto["also_report_profiles"]]
    if grid is None:
        grid, source = load_candidates("grid")
    grid = grid.reset_index(drop=True)
    lat, lon = grid["lat"].to_numpy(float), grid["lon"].to_numpy(float)
    rng = np.random.default_rng(seed)
    rows, base = [], []
    targets_needed = sorted({c["expected_target"] for c in cfg["candidates"]})
    for prof in profiles:
        for tid in targets_needed:
            _, feats = get_target(tid)
            sc = score(feats, grid, profile=prof)
            ok = sc["coverage"].to_numpy() >= 0.5
            si = np.where(ok, sc["si"].to_numpy(), np.nan)
            valid = np.sort(si[~np.isnan(si)])
            pct = lambda v: 100.0 * np.searchsorted(valid, v, side="right") / len(valid)  # noqa: E731
            for c in (x for x in cfg["candidates"] if x["expected_target"] == tid):
                near = _haversine_km(c["lat"], c["lon"], lat, lon) <= c["radius_km"]
                cand = si[near]
                best = np.nanmax(cand) if near.any() and np.isfinite(cand).any() else np.nan
                p = pct(best) if np.isfinite(best) else np.nan
                rows.append({"candidate": c["id"], "country": c["country"], "income": c["income"],
                             "target": tid, "profile": prof, "cells_in_radius": int(near.sum()),
                             "best_si": round(float(best), 1) if np.isfinite(best) else None,
                             "percentile": round(float(p), 1) if np.isfinite(p) else None,
                             "pass": bool(np.isfinite(p) and p >= proto["pass_percentile"]),
                             "strong_pass": bool(np.isfinite(p) and p >= proto["strong_pass_percentile"])})
                # Random baseline: same radius, random scored land cells as centres.
                idx = np.flatnonzero(~np.isnan(si))
                for k in rng.choice(idx, size=min(n_random, len(idx)), replace=False):
                    m = _haversine_km(lat[k], lon[k], lat, lon) <= c["radius_km"]
                    b = np.nanmax(si[m])
                    base.append({"profile": prof, "candidate": c["id"], "pass": pct(b) >= proto["pass_percentile"]})
    detail = pd.DataFrame(rows)
    # Candidates later found to be already studied (amendments) are reported, but not counted as novel.
    known = {a["candidate"] for a in cfg.get("amendments", []) if a.get("type") == "reclassified_known"}
    detail["known_after_freeze"] = detail["candidate"].isin(known)
    bl = pd.DataFrame(base).groupby("profile")["pass"].mean().rename("random_pass_rate")
    summary = detail.groupby("profile").agg(candidates=("candidate", "count"), passed=("pass", "sum"),
                                            strong=("strong_pass", "sum")).join(bl)
    summary["pass_rate"] = summary["passed"] / summary["candidates"]
    novel = detail[~detail["known_after_freeze"]].groupby("profile").agg(
        novel_candidates=("candidate", "count"), novel_passed=("pass", "sum"))
    summary = summary.join(novel)
    return detail, summary.round(3)


def to_records(frame: pd.DataFrame) -> list[dict]:
    cols = [c for c in ["id", "cell_id", "name", "country", "iso3", "lat", "lon", "income_group",
                        "si", "income_bonus", "novelty_bonus", "opportunity", "rank_opportunity", "rank_si",
                        "priority_reason", "coverage", "known_analog", "explanation"] if c in frame.columns]
    cols += [f"fam_{f}" for f in family_ids() if f"fam_{f}" in frame.columns]
    return [_plain(r) for r in frame[cols].to_dict(orient="records")]


def _plain(v):
    """Recursively convert numpy/pandas scalars to JSON-safe Python values (NaN -> None)."""
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else round(float(v), 3)
    return v
