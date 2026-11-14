# Running the Earth Engine extraction (Step B)

**Easiest way:** double-click `start.bat` in the project folder (macOS/Linux: `./start.sh`). It starts the local server
and opens the pipeline panel at http://127.0.0.1:8000/. Every step below is a button there, with live logs, a CSV
drop zone for the Drive exports and a "next step" hint. The commands below do the same thing from a terminal.

Earth Engine credentials live on a team member's machine, so this step runs there.
All commands from `backend/` (Windows PowerShell or any shell). Python 3.10+.

```bash
pip install -r requirements.txt
python -m unittest discover -s tests        # 29 tests must pass
```

## 1. Smoke test: Turkey box, 25 km (~190 land cells, a few minutes)
```bash
python -m analog_atlas.cli build-grid --km 25 --bbox 26 36 31 39 --countries
python -m analog_atlas.cli extract-earth --project space-apps-analog --mode sample
```
Prints grid vs literature values for catalog sites inside the box (Kula, Lake Salda). Raw values: `data/raw_sample.csv`.
Expected ballpark at Salda (37.55N, 29.68E): slope a few degrees, albedo 0.15-0.3, temp_min about -10..0 degC.
`ti_rel` and `dust_activity` are percentiles over the processed cells, so inside a small box they are only relative to
that box; they become Earth-wide after step 3.

## 2. Global coarse scan: 50 km (~63 000 land cells -> 13 export tasks of <= 5000 cells)
```bash
python -m analog_atlas.cli build-grid --km 50 --countries
python -m analog_atlas.cli extract-earth --project space-apps-analog --mode export --no-s2
python -m analog_atlas.cli export-status --project space-apps-analog
```
Only land cells are exported (ISO3 assigned; Antarctica = ATA). `--no-s2` skips the Sentinel-2 Fe/clay ratios, the
heaviest layer (those two proxies stay empty). Tasks write CSVs to the Drive folder `analog_atlas`.
Keep `data/grid.parquet`: merging joins on `cell_id`.

## 3. Merge, check, embed
Download every `analog_atlas_50km_*.csv` from Drive into `backend/data/exports/`, then:
```bash
python -m analog_atlas.cli merge-exports
python -m analog_atlas.cli find --target cerberus --profile landing
python -m analog_atlas.cli check-discoveries
python -m analog_atlas.cli export-offline --embed ../index.html
python -m analog_atlas.cli verify-dois
```
`export-offline --embed` writes the discoveries for every preset x profile into `index.html`, so the demo shows real
discoveries even when the API is down. `data/earth_features.parquet` (50 km) is small: commit it, the API deploy needs it.
