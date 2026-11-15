# Analog Atlas: backend

Python engine behind [Analog Atlas](../README.md). It scans the whole Earth grid for the places most similar to a Moon
or Mars target region, explains each match, and treats the Global South as a **priority, never a filter**. The browser
app runs the same metric on its own; this package adds the global grid, the Earth Engine extraction, the validation
reports and an HTTP API.

## Pipeline

```
NASA / ESA / JAXA open data (Google Earth Engine)          Moon / Mars target regions
        │  extract/earth_gee.py                                 │  config/targets.json (literature values)
        ▼                                                       ▼
~50 km land grid ──► 24 features per cell ──────────►  target feature vector
(grid.py, 58,289 cells)   data/earth_features.parquet
                                   │
                                   ▼
          scoring.py    SI = 100 · (1 − √(Σ w·Δ² / Σ w))     fixed physical ranges, NaN-aware
                                   │
                                   ▼
          priority.py   opportunity = SI + income + novelty + access bonuses   (only when SI ≥ 60)
                                   │
                                   ▼
          pipeline.py   anchors · 150 km discovery regions · quota selection · "strongest / breaks on"
                                   │
                  cli.py (out/*.json)  ·  api.py (HTTP)  ·  server.py (app + API + pipeline runner)
```

## Global South priority

| World Bank group | Bonus (SI points) |
|---|---|
| Low income (LIC) | +10 |
| Lower-middle income (LMC) | +7 |
| Upper-middle income (UMC) | +4 |
| High income (HIC) / unclassified | 0 |

Novelty adds up to +5 (distance to the nearest past analog campaign, full at 500 km) and access up to +3 (travel time to
the nearest city).

- **Nothing is removed.** SI is always reported unchanged next to `opportunity`.
- **Bonuses apply only when SI ≥ 60**, so a weak analog cannot rise because of where it is.
- **Bonuses are bounded.** A candidate can only overtake one that is at most its total bonus better.
- In `quota` mode (default) at least 10 of the top 20 discoveries are Global South regions; the rest are the best by
  pure SI. Everything is set in `config/priority.json`. Income data: World Bank API (CC BY 4.0).

## Install and test

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v       # 36 tests; the server tests need fastapi + httpx
```

Python 3.11 or newer. Earth Engine steps also need `earthengine-api` and a Cloud project with Earth Engine enabled.

## Command line

`python -m analog_atlas.cli <command>`

| Command | What it does |
|---|---|
| `validate` | Ranks of the frozen literature anchors (pure SI), per profile |
| `demo [--target ID] [--profile P]` | Scores the Moon / Mars targets against the 16-site catalog |
| `find --target ID [--profile P]` | Anchor & Discover: anchors plus clustered grid discoveries → `out/*.json` |
| `score --target ID [--profile P] [--top N]` | Raw ranking from the grid (or the catalog if no grid) |
| `check-discoveries` | Frozen literature checklist against the global grid, with a random baseline |
| `build-grid --km 50 [--bbox W S E N] [--countries]` | Builds the near-equal-area grid → `data/grid.parquet` |
| `extract-earth --project GCP_ID [--mode sample\|export]` | Earth Engine feature extraction (land cells only) |
| `export-status --project GCP_ID` | State of the Earth Engine export tasks |
| `merge-exports [--dir data/exports]` | Drive CSVs + grid → `data/earth_features.parquet` |
| `export-offline [--embed ../index.html]` | Precomputes preset discoveries for the offline demo |
| `verify-dois [--html ../index.html]` | Checks every reference DOI on Crossref |
| `fetch-income` | Refreshes `data/income_groups.csv` from the World Bank |

The Earth Engine workflow, step by step: [`../docs/RUN_EARTH_ENGINE.md`](../docs/RUN_EARTH_ENGINE.md).

## HTTP API

```bash
uvicorn analog_atlas.api:app --port 8000
```

| Route | Purpose |
|---|---|
| `GET /health` | Liveness and data status |
| `GET /targets`, `GET /config` | Preset targets, feature set and profiles |
| `POST /score` | Score a feature vector against the catalog |
| `POST /find-analogs` | Anchors + discoveries for a preset or custom target |

`analog_atlas.server:app` (used by `start.bat` / `start.sh`) serves the app, this API and the background job runner for
the in-app Data pipeline drawer on one port. `Dockerfile` deploys the API to Hugging Face Spaces, Render or any
container host (port 7860 by default).

## Files

| Path | Role |
|---|---|
| `config/features.json` | Feature set, fixed ranges, families, profiles and data source per feature (single source of truth) |
| `config/priority.json` | Bonuses, eligibility threshold, clustering and selection mode |
| `config/targets.json` | 7 Moon / Mars target regions (literature values) |
| `config/anchors.json` | Validation anchor pairs, frozen before the first run |
| `config/discovery_checklist.json` | 10 frozen literature candidates for the harder discovery test |
| `data/catalog_sites.json` | 16 documented Earth analog sites with sources |
| `data/campaigns.csv` | 41 analog field campaigns, one cited source each |
| `data/income_groups.csv` | World Bank income groups (217 economies) |
| `data/earth_features.parquet` | The 58,289-cell Earth grid with its 24 features |
| `analog_atlas/scoring.py` | Vectorized similarity engine and explanations |
| `analog_atlas/priority.py` | Global South priority layer |
| `analog_atlas/pipeline.py` | Anchor & Discover, clustering, selection |
| `analog_atlas/extract/earth_gee.py` | Earth Engine extraction and post-processing |

## Known limits

- Moon and Mars target vectors are literature estimates, not a PDS extraction.
- Mineral and ground-ice values on the grid are rough proxies and are labelled as such.
- Roughness, crater density, rock abundance, plagioclase, evaporite, caves and landform have no calibrated global layer
  yet: they are missing on the grid and the scorer skips them (coverage is reported).
