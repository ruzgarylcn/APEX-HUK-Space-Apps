"""Command line entry point:  python -m analog_atlas.cli <command> [options]

  fetch-income                       World Bank income groups -> data/income_groups.csv
  demo   [--target ID] [--profile P] Score Moon/Mars targets against the 16-site catalog
  validate                           Rank of the frozen literature anchors (pure SI)
  build-grid --km 10 [--bbox W S E N] [--countries]   -> data/grid.parquet
  extract-earth --project GCP_ID [--mode sample|export] [--no-s2]  (Google Earth Engine, land cells only)
  export-status --project GCP_ID     State of the Earth Engine export tasks
  merge-exports [--dir data/exports] Drive CSVs + grid -> data/earth_features.parquet
  score --target ID [--profile P] [--top N] [--source auto|grid|catalog]  -> out/*.json
  find --target ID [--profile P]     Anchor & Discover: anchors + clustered discoveries -> out/*.json
  check-discoveries                  Frozen literature checklist vs the global grid
  export-offline [--embed ../index.html]  Precompute preset x profile discoveries for the offline demo
  verify-dois [--html ../index.html] Check every reference DOI on Crossref
"""
from __future__ import annotations

import argparse
import json
import sys

import pandas as pd

from .config import DATA_DIR, OUT_DIR, features_config, targets
from .pipeline import EARTH_FEATURES_PATH, get_target, load_candidates, rank, to_records


def _print_table(target: dict, profile: str, head: pd.DataFrame) -> None:
    print(f"\n=== {target['name']} ({target['planet']}) - profile: {profile} ===")
    print(f"{'opp#':>4} {'SI#':>4}  {'site':<30} {'income':<4} {'SI':>5} {'bonus':>5} {'opp':>6}  breaks on")
    for _, r in head.iterrows():
        label = r.get("name") or r.get("cell_id")
        breaks = ", ".join(b["feature"] for b in r["explanation"]["breaks_on"])
        print(f"{r['rank_opportunity']:>4} {r['rank_si']:>4}  {str(label)[:30]:<30} {r['income_group']:<4} "
              f"{r['si']:5.1f} {r['income_bonus']:5.0f} {r['opportunity']:6.1f}  {breaks}")


def cmd_demo(args) -> None:
    ids = [args.target] if args.target else [t["id"] for t in targets()]
    cands, source = load_candidates("catalog")
    OUT_DIR.mkdir(exist_ok=True)
    for tid in ids:
        target, feats = get_target(tid)
        head = rank(feats, cands, profile=args.profile, top=args.top)
        _print_table(target, args.profile, head)
        (OUT_DIR / f"demo_{tid}_{args.profile}.json").write_text(
            json.dumps({"target": tid, "profile": args.profile, "source": source,
                        "results": to_records(head)}, indent=1, ensure_ascii=False), encoding="utf-8")


def cmd_score(args) -> None:
    target, feats = get_target(args.target)
    cands, source = load_candidates(args.source)
    head = rank(feats, cands, profile=args.profile, top=args.top)
    _print_table(target, args.profile, head)
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"score_{args.target}_{args.profile}_{source}.json"
    path.write_text(json.dumps({"target": args.target, "profile": args.profile, "source": source,
                                "results": to_records(head)}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {path}")


def cmd_validate(args) -> None:
    from .pipeline import validate, validation_summary

    detail = validate()
    summary = validation_summary(detail)
    print("Anchor ranks by pure SI (catalog of", int(detail["of"].iloc[0]), "sites):\n")
    piv = detail.pivot_table(index=["target", "anchor"], columns="profile", values="rank", aggfunc="min")
    print(piv.to_string())
    print("\nSummary (best anchor per target):\n")
    print(summary.to_string())
    OUT_DIR.mkdir(exist_ok=True)
    detail.to_csv(OUT_DIR / "validation_detail.csv", index=False)
    summary.to_csv(OUT_DIR / "validation_summary.csv")
    print(f"\nwrote {OUT_DIR / 'validation_detail.csv'} and validation_summary.csv")


def cmd_check_discoveries(_args) -> None:
    from .pipeline import check_discoveries

    detail, summary = check_discoveries()
    print("Frozen discovery checklist vs global grid (pure SI, percentile among land cells):\n")
    print(detail.pivot_table(index=["candidate", "target"], columns="profile", values="percentile").to_string())
    print("\nSummary (pass = >= 90th percentile):\n")
    print(summary.to_string())
    OUT_DIR.mkdir(exist_ok=True)
    detail.to_csv(OUT_DIR / "discovery_check_detail.csv", index=False)
    summary.to_csv(OUT_DIR / "discovery_check_summary.csv")


def cmd_fetch_income(_args) -> None:
    from .priority import fetch_income_groups

    frame = fetch_income_groups()
    print(f"{len(frame)} countries:", frame["income"].value_counts().to_dict())


def cmd_build_grid(args) -> None:
    from .grid import build_grid

    grid = build_grid(args.km, tuple(args.bbox) if args.bbox else None)
    if args.countries:
        from .countries import assign_countries
        grid = assign_countries(grid)
    path = DATA_DIR / "grid.parquet"
    grid.to_parquet(path, index=False)
    print(f"{len(grid):,} cells -> {path}")


def cmd_extract_earth(args) -> None:
    from .extract import earth_gee

    earth_gee.init(args.project)
    grid = pd.read_parquet(DATA_DIR / "grid.parquet")
    land = earth_gee.land_only(grid)
    print(f"{len(grid):,} grid cells, {len(land):,} on land (iso3 assigned)")
    s2 = not args.no_s2
    if args.mode == "export":
        tag = args.tag or f"{int(round(grid['half_dlat'].iloc[0] * 2 * 111.32))}km"
        for i, part in earth_gee.chunks(land):
            task = earth_gee.export_cells(part, description=f"analog_atlas_{tag}_{i:03d}", include_s2=s2)
            print("started", task.id, f"analog_atlas_{tag}_{i:03d}", "cells", len(part))
        print("\nTrack with:  python -m analog_atlas.cli export-status --project", args.project)
        print("Then download the CSVs from Drive folder 'analog_atlas' into backend/data/exports/ and run merge-exports.")
        return
    raw = earth_gee.sample_cells(grid, include_s2=s2)
    (DATA_DIR / "raw_sample.csv").write_text(raw.to_csv(index=False), encoding="utf-8")
    feats = earth_gee.postprocess(raw)
    feats.to_parquet(EARTH_FEATURES_PATH, index=False)
    print(f"{len(feats):,} land cells -> {EARTH_FEATURES_PATH}  (raw values: data/raw_sample.csv)")
    _sanity_report(feats)


def _sanity_report(feats: pd.DataFrame) -> None:
    """Compare extracted cells with the literature values of catalog sites inside the extracted area."""
    from .pipeline import _haversine_km, load_catalog
    from .config import numeric_keys

    cat = load_catalog()
    lat, lon = feats["lat"].to_numpy(float), feats["lon"].to_numpy(float)
    for _, s in cat.iterrows():
        d = _haversine_km(s["lat"], s["lon"], lat, lon)
        if d.min() > 30:
            continue
        cell = feats.iloc[int(d.argmin())]
        print(f"\nSanity check - {s['name']}: nearest cell {cell['cell_id']} ({d.min():.0f} km)")
        print(f"  {'feature':<24}{'grid':>10}{'catalog':>10}")
        for k in numeric_keys():
            print(f"  {k:<24}{cell[k]:>10.3g}{s[k]:>10.3g}")
    print("\nNote: ti_rel and dust_activity are percentiles over the cells processed together; in a small sample\n"
          "box they are relative to that box only. They become Earth-wide after merge-exports on the global set.")
    print("\nnon-null share per feature:")
    print(feats[numeric_keys()].notna().mean().round(2).to_string())


def cmd_export_status(args) -> None:
    from .extract import earth_gee
    import ee

    earth_gee.init(args.project)
    for t in ee.batch.Task.list()[: args.n]:
        s = t.status()
        print(f"{s.get('state'):<10} {s.get('description'):<32} {s.get('error_message', '')}")


def cmd_merge_exports(args) -> None:
    from pathlib import Path

    from .extract import earth_gee

    folder = Path(args.dir)
    paths = sorted(folder.glob("*.csv"))
    print(f"{len(paths)} CSV files in {folder}")
    grid = pd.read_parquet(DATA_DIR / "grid.parquet")
    feats = earth_gee.merge_exports(paths, grid, fill_dem_project=args.fill_dem_project)
    feats.to_parquet(EARTH_FEATURES_PATH, index=False)
    print(f"{len(feats):,} land cells -> {EARTH_FEATURES_PATH}")
    from .config import numeric_keys
    print(feats[numeric_keys()].notna().mean().round(2).to_string())


def cmd_verify_dois(args) -> None:
    """Check every DOI in the frontend's #citation-db against Crossref (https://api.crossref.org/works/<doi>)."""
    import re
    import time
    from pathlib import Path

    import requests

    html = Path(args.html).read_text(encoding="utf-8")
    cites = json.loads(re.search(r'id="citation-db">(.*?)</script>', html, re.S).group(1))
    rows = []
    for c in cites:
        m = re.search(r"doi\.org/(10\.[^\s?#]+)", c.get("sourceUrl") or "")
        doi = c.get("doi") or (m.group(1) if m else None)
        if not doi:
            continue
        r = requests.get(f"https://api.crossref.org/works/{doi}", timeout=30,
                         headers={"User-Agent": "AnalogAtlas/2 (NASA Space Apps 2026)"})
        title = (r.json()["message"].get("title") or [""])[0] if r.ok else ""
        ok = r.ok and title.lower()[:40] == c["title"].lower()[:40]
        rows.append({"id": c["id"], "doi": doi, "http": r.status_code, "title_match": ok, "crossref_title": title})
        print(f"{c['id']}  {r.status_code}  {'OK   ' if ok else 'CHECK'}  {doi}  {title[:70]}")
        time.sleep(0.2)
    OUT_DIR.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT_DIR / "doi_check.csv", index=False)


def cmd_find(args) -> None:
    from .pipeline import find_analogs

    r = find_analogs(args.target, profile=args.profile, top=args.top)
    print(f"\n=== {r['target']['name']} - profile {args.profile} - selection: {r['selection_mode']} ===")
    print("\nValidation anchors (catalog, pure SI):")
    for a in r["anchors"][:8]:
        flag = " <- literature anchor" if a["is_anchor"] else ""
        print(f"  {a['rank_si']:>2}. {a['name'][:32]:<32} SI {a['si']:5.1f}  opp {a['opportunity']:5.1f}{flag}")
    print(f"\nNew discoveries ({r['discovery_source']}, {r['cells_scored']:,} cells scored):")
    if not r["discoveries"]:
        print("  none - run the Earth Engine extraction first (data/earth_features.parquet)")
    for d in r["discoveries"]:
        known = " KNOWN-NEARBY" if d.get("known_nearby") else ""
        acc = d.get("access_minutes")
        print(f"  {d['iso3'] or '---'} {d['income_group']:<3} {d['lat']:7.2f} {d['lon']:8.2f}  SI {d['si']:5.1f} "
              f"(p{d['si_percentile']})  opp {d['opportunity']:5.1f}  cells {d['region_cells']:>3}  "
              f"campaign {d['campaign_km']:5.0f} km  access {acc if acc is None else round(acc / 60, 1)} h  "
              f"[{d['slot']}]{known}  breaks: {', '.join(b['feature'] for b in d['explanation']['breaks_on'])}")
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"find_{args.target}_{args.profile}.json"
    path.write_text(json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {path}")


def cmd_export_offline(args) -> None:
    """Precompute discoveries for every preset x profile; optionally embed them into the frontend."""
    import datetime
    import re
    from pathlib import Path

    from .pipeline import _plain, find_analogs

    out = {}
    stamp = datetime.date.today().isoformat()
    for t in targets():
        for prof in features_config()["profiles"]:
            r = find_analogs(t["id"], profile=prof, top=args.top)
            out[f"{t['id']}|{prof}"] = {"discoveries": r["discoveries"], "selection_mode": r["selection_mode"],
                                        "cells_scored": r["cells_scored"], "generated": stamp, "source": r["discovery_source"]}
            print(f"{t['id']:<11} {prof:<9} {len(r['discoveries'])} discoveries")
    OUT_DIR.mkdir(exist_ok=True)
    text = json.dumps(_plain(out), ensure_ascii=False, separators=(",", ":"))
    (OUT_DIR / "offline_results.json").write_text(text, encoding="utf-8")
    print(f"wrote {OUT_DIR / 'offline_results.json'} ({len(text) / 1024:.0f} KB)")
    if args.embed:
        html_path = Path(args.embed)
        html = html_path.read_text(encoding="utf-8")
        new, n = re.subn(r'(<script type="application/json" id="offline-results">)(.*?)(</script>)',
                         lambda m: m.group(1) + "\n" + text + "\n" + m.group(3), html, count=1, flags=re.S)
        if n != 1:
            raise SystemExit("offline-results block not found in " + str(html_path))
        html_path.write_text(new, encoding="utf-8")
        print(f"embedded into {html_path}")


def main(argv=None) -> None:
    profiles = list(features_config()["profiles"])
    p = argparse.ArgumentParser(prog="analog_atlas")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo"); d.set_defaults(fn=cmd_demo)
    d.add_argument("--target"); d.add_argument("--profile", default="landing", choices=profiles)
    d.add_argument("--top", type=int, default=12)

    s = sub.add_parser("score"); s.set_defaults(fn=cmd_score)
    s.add_argument("--target", required=True); s.add_argument("--profile", default="landing", choices=profiles)
    s.add_argument("--top", type=int, default=50); s.add_argument("--source", default="auto", choices=["auto", "grid", "catalog"])

    f = sub.add_parser("fetch-income"); f.set_defaults(fn=cmd_fetch_income)

    v = sub.add_parser("validate"); v.set_defaults(fn=cmd_validate)

    k = sub.add_parser("check-discoveries"); k.set_defaults(fn=cmd_check_discoveries)

    g = sub.add_parser("build-grid"); g.set_defaults(fn=cmd_build_grid)
    g.add_argument("--km", type=float, default=10.0); g.add_argument("--bbox", type=float, nargs=4)
    g.add_argument("--countries", action="store_true")

    e = sub.add_parser("extract-earth"); e.set_defaults(fn=cmd_extract_earth)
    e.add_argument("--project", required=True); e.add_argument("--mode", default="sample", choices=["sample", "export"])
    e.add_argument("--no-s2", action="store_true", help="skip Sentinel-2 Fe/clay ratios (much faster)")
    e.add_argument("--tag", help="name tag for export tasks (default: grid size)")

    es = sub.add_parser("export-status"); es.set_defaults(fn=cmd_export_status)
    es.add_argument("--project", required=True); es.add_argument("-n", type=int, default=40)

    m = sub.add_parser("merge-exports"); m.set_defaults(fn=cmd_merge_exports)
    m.add_argument("--dir", default=str(DATA_DIR / "exports"))
    m.add_argument("--fill-dem-project", help="Earth Engine project: fill polar terrain (outside NASADEM) from Copernicus GLO-30")

    vd = sub.add_parser("verify-dois"); vd.set_defaults(fn=cmd_verify_dois)
    vd.add_argument("--html", default=str(DATA_DIR.parent.parent / "index.html"))

    fa = sub.add_parser("find"); fa.set_defaults(fn=cmd_find)
    fa.add_argument("--target", required=True); fa.add_argument("--profile", default="science", choices=profiles)
    fa.add_argument("--top", type=int, default=20)

    ox = sub.add_parser("export-offline"); ox.set_defaults(fn=cmd_export_offline)
    ox.add_argument("--top", type=int, default=12); ox.add_argument("--embed", help="path to index.html to embed into")

    args = p.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows consoles default to cp1252
    except (AttributeError, ValueError):
        pass
    args.fn(args)


if __name__ == "__main__":
    main()
