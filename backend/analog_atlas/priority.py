"""Global South priority layer.

Developing countries are a PRIORITY, not a filter: nothing is removed from the ranking.

    opportunity = SI + income_bonus + novelty_bonus + access_bonus   (bonuses only if SI >= min_si_for_bonus)

SI (pure physical similarity) is always kept next to `opportunity`, so the physics and
the policy choice stay separable and auditable.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DATA_DIR, priority_config

INCOME_CSV = DATA_DIR / "income_groups.csv"
WB_URL = "https://api.worldbank.org/v2/country?format=json&per_page=400"


def fetch_income_groups(path=INCOME_CSV) -> pd.DataFrame:
    """Download the World Bank income classification (open data, CC BY 4.0) to CSV."""
    import requests

    resp = requests.get(WB_URL, timeout=60)
    resp.raise_for_status()
    rows = []
    for c in resp.json()[1]:
        if c["region"]["id"] == "NA":          # aggregates such as "World", "Euro area"
            continue
        income = c["incomeLevel"]["id"]
        rows.append({"iso3": c["id"], "name": c["name"], "region": c["region"]["value"],
                     "income": income if income in ("LIC", "LMC", "UMC", "HIC") else "NA"})
    frame = pd.DataFrame(rows).sort_values("iso3")
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return frame


def load_income_groups(path=INCOME_CSV) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{path} missing - run: python -m analog_atlas.cli fetch-income")
    return pd.read_csv(path, keep_default_na=False)


def apply_priority(scored: pd.DataFrame, iso3_col: str = "iso3",
                   income: pd.DataFrame | None = None, novelty_col: str | None = None) -> pd.DataFrame:
    """Add income group, bonus, opportunity score and rank (by opportunity, then SI)."""
    cfg = priority_config()
    income = load_income_groups() if income is None else income
    lookup = dict(zip(income["iso3"], income["income"]))
    out = scored.copy()
    out["income_group"] = out[iso3_col].map(lambda c: lookup.get(c, "NA") if isinstance(c, str) else "NA")
    eligible = out["si"] >= cfg["min_si_for_bonus"]
    base_bonus = out["income_group"].map(cfg["income_bonus"]).fillna(0).astype(float)
    out["income_bonus"] = np.where(eligible, base_bonus, 0.0)
    if novelty_col and novelty_col in out:
        nov = np.clip(out[novelty_col].fillna(0).to_numpy(float), 0, 1) * cfg["novelty"]["max_bonus"]
        out["novelty_bonus"] = np.where(eligible, nov, 0.0)
    else:
        out["novelty_bonus"] = 0.0
    if "access_minutes" in out:
        out["access_bonus"] = np.where(eligible, access_bonus(out["access_minutes"], cfg), 0.0)
        out["hard_access"] = out["access_minutes"].to_numpy(float) > cfg["access"]["hard_access_minutes"]
    else:
        out["access_bonus"] = 0.0
    out["opportunity"] = out["si"] + out["income_bonus"] + out["novelty_bonus"] + out["access_bonus"]
    out["priority_reason"] = np.where(
        out["income_bonus"] > 0,
        "Global South priority: " + out["income_group"].map(cfg["income_label"]) + " (+" + out["income_bonus"].map("{:.0f}".format) + ")",
        np.where(eligible, "", f"SI below {cfg['min_si_for_bonus']}: no priority bonus"),
    )
    out = out.sort_values(["opportunity", "si"], ascending=False)
    out["rank_opportunity"] = np.arange(1, len(out) + 1)
    out["rank_si"] = out["si"].rank(ascending=False, method="first").astype(int)
    return out


def access_bonus(minutes, cfg: dict | None = None) -> np.ndarray:
    """Linear access bonus: max at <= full_bonus_minutes, 0 at >= zero_bonus_minutes, 0 when unknown."""
    a = (cfg or priority_config())["access"]
    m = np.asarray(minutes, dtype=float)
    frac = (a["zero_bonus_minutes"] - m) / (a["zero_bonus_minutes"] - a["full_bonus_minutes"])
    return np.where(np.isnan(m), 0.0, a["max_bonus"] * np.clip(frac, 0.0, 1.0))


def select(prioritized: pd.DataFrame, n: int, cfg: dict | None = None) -> pd.DataFrame:
    """Pick n rows per priority.json -> selection (HANDOFF 6.1: 'bonus' or 'quota').

    quota: within the first top_n, at least min_global_south Global South rows (best opportunity
    first, SI >= min_si_for_bonus); the remaining slots go to the best pure SI. `slot` says why a row is
    there. Rows are returned in opportunity order.
    """
    cfg = cfg or priority_config()
    sel = cfg["selection"]
    if sel["mode"] == "bonus" or prioritized.empty:
        out = prioritized.head(n).copy()
        out["slot"] = "opportunity"
        return out
    q = sel["quota"]
    k = min(n, q["top_n"])
    gs = prioritized[prioritized["income_group"].isin(q["global_south_groups"])
                     & (prioritized["si"] >= cfg["min_si_for_bonus"])]
    need = min(q["min_global_south"] * k // q["top_n"], len(gs))
    chosen = list(gs.index[:need])
    rest = prioritized.drop(index=chosen).sort_values("si", ascending=False, kind="mergesort")
    chosen += list(rest.index[: k - len(chosen)])
    quota_ids = set(chosen[:need])
    out = prioritized.loc[chosen].copy()
    out["slot"] = ["global_south_quota" if i in quota_ids else "pure_si" for i in out.index]
    out = out.sort_values(["opportunity", "si"], ascending=False, kind="mergesort")
    if n > k:
        tail = prioritized.drop(index=out.index).head(n - k).copy()
        tail["slot"] = "opportunity"
        out = pd.concat([out, tail])
    return out
