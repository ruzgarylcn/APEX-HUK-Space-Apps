"""Command line entry point:  python -m analog_atlas.cli <command> [options]

  fetch-income                       World Bank income groups -> data/income_groups.csv
  demo   [--target ID] [--profile P] Score Moon/Mars targets against the 12-site catalog
  build-grid --km 10 [--bbox W S E N] [--countries]   -> data/grid.parquet
  extract-earth --project GCP_ID [--mode sample|export]  (Google Earth Engine)
  score --target ID [--profile P] [--top N] [--source auto|grid|catalog]  -> out/*.json
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
    if args.mode == "export":
        tiles = grid.groupby((grid["lat"] // 10).astype(int))
        for band, part in tiles:
            task = earth_gee.export_cells(part, description=f"analog_atlas_band_{band}")
            print("started", task.id, "rows", len(part))
        print("When the Drive exports finish, merge the CSVs and run postprocess().")
        return
    raw = earth_gee.sample_cells(grid)
    feats = earth_gee.postprocess(raw)
    feats.to_parquet(EARTH_FEATURES_PATH, index=False)
    print(f"{len(feats):,} land cells -> {EARTH_FEATURES_PATH}")


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

    args = p.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows consoles default to cp1252
    except (AttributeError, ValueError):
        pass
    args.fn(args)


if __name__ == "__main__":
    main()
