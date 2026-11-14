"""Earth feature extraction with Google Earth Engine (NASA datasets hosted on GEE).

STATUS: written against the public GEE catalog; unit-tested offline (postprocess, merge). Run it with
`earthengine authenticate` on a GEE-enabled Google Cloud project (see docs/RUN_EARTH_ENGINE.md).

Fixes over the first draft: PET from TerraClimate (MOD16A2 masks barren land and deserts, i.e. our
candidates), Oxford MAP accessibility band (bonus input, not a feature), optional Sentinel-2,
explicit CSV selectors (no per-row geometry), land-only exports of <= 5000 cells per task.

Two stages:
  1. `raw_stack()` builds one multi-band ee.Image of RAW measurements at ~1 km.
     `sample_cells()` (small areas, direct) or `export_cells()` (global, Drive export)
     reduces it over grid-cell rectangles.
  2. `postprocess()` (pure pandas, runs locally) turns raw columns into the v2 features:
     percentiles (ti_rel, dust_activity), proxies (minerals, ground ice) and the computed
     sun angle. Features with no global source yet stay NaN; the scorer skips NaNs.

Proxy formulas are deliberately simple and labelled; they are the first thing to
improve once the end-to-end pipeline runs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..features import noon_sun_elevation

YEARS = ("2019-01-01", "2024-01-01")
SCALE_M = 1000


def _ee():
    import ee  # noqa: WPS433 - optional dependency
    return ee


def init(project: str | None = None):
    ee = _ee()
    ee.Initialize(project=project)
    return ee


def raw_stack(include_s2: bool = True):
    """Multi-band image of raw measurements (band names are the raw_* columns)."""
    ee = _ee()
    start, end = YEARS

    dem = ee.Image("NASA/NASADEM_HGT/001").select("elevation")
    slope = ee.Terrain.slope(dem).rename("raw_slope")
    slope_sq = slope.multiply(slope).rename("raw_slope_sq")   # cell std = sqrt(mean(s^2) - mean(s)^2)
    relief = (dem.focalMax(2500, "circle", "meters").subtract(dem.focalMin(2500, "circle", "meters"))
              .rename("raw_relief_5km"))
    tri = dem.subtract(dem.focalMean(90, "circle", "meters")).abs().rename("raw_tri")

    lst = ee.ImageCollection("MODIS/061/MOD11A2").filterDate(start, end)
    to_c = lambda img, band: img.select(band).multiply(0.02).subtract(273.15)  # noqa: E731
    day = lst.map(lambda i: to_c(i, "LST_Day_1km").rename("d"))
    night = lst.map(lambda i: to_c(i, "LST_Night_1km").rename("n"))
    t_min = night.reduce(ee.Reducer.percentile([5])).rename("raw_temp_min")
    swing = lst.map(lambda i: to_c(i, "LST_Day_1km").subtract(to_c(i, "LST_Night_1km")).rename("s")) \
               .median().rename("raw_diurnal_range")
    frost = night.map(lambda i: i.lt(0)).mean().rename("raw_frost_fraction")
    # Mean LST over day and night: both collections must share one band name before merging (else EE rejects
    # the heterogeneous collection: "Expected a homogeneous image collection").
    maat = day.map(lambda i: i.rename("t")).merge(night.map(lambda i: i.rename("t"))).mean().rename("raw_mean_lst")

    albedo = (ee.ImageCollection("MODIS/061/MCD43A3").filterDate(start, end)
              .select("Albedo_WSA_shortwave").median().multiply(0.001).rename("raw_albedo"))
    # Apparent thermal inertia ATI = (1 - albedo) / (Tday - Tnight); percentile taken in postprocess.
    ati = ee.Image(1).subtract(albedo).divide(swing.max(1)).rename("raw_ati")

    ndvi = (ee.ImageCollection("MODIS/061/MOD13A2").filterDate(start, end)
            .select("NDVI").median().multiply(0.0001).rename("raw_ndvi"))

    precip = (ee.ImageCollection("NASA/GPM_L3/IMERG_MONTHLY_V07").filterDate(start, end)
              .select("precipitation").mean().multiply(24 * 365.25).rename("raw_precip_mm"))
    # TerraClimate PET (mm/month, scale 0.1) covers all land; MOD16A2 masks barren land and deserts.
    n_years = int(end[:4]) - int(start[:4])
    pet = (ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterDate(start, end)
           .select("pet").sum().multiply(0.1 / n_years).rename("raw_pet_mm"))

    # MERRA-2 aerosols are hourly; one image per day (00 UTC) keeps the annual mean cheap.
    dust = (ee.ImageCollection("NASA/GSFC/MERRA/aer/2").filterDate("2022-01-01", "2023-01-01")
            .filter(ee.Filter.calendarRange(0, 0, "hour")).select("DUEXTTAU").mean().rename("raw_dust_aod"))
    # Travel time to the nearest city (minutes). Not a feature: input to the access bonus.
    # Malaria Atlas Project asset (replaces the deprecated Oxford/MAP/accessibility_to_cities_2015_v1_0 id).
    access = (ee.Image("projects/malariaatlasproject/assets/accessibility/accessibility_to_cities/2015_v1_0")
              .select("accessibility").rename("raw_access_minutes"))

    aster = ee.Image("NASA/ASTER_GED/AG100_003")
    e = {b: aster.select(f"emissivity_band{b}").multiply(0.001) for b in (10, 11, 12, 13, 14)}
    mafic = e[12].divide(e[13]).rename("raw_mafic_index")             # Ninomiya MI
    quartz = e[11].multiply(e[11]).divide(e[10].multiply(e[12])).rename("raw_quartz_index")
    carbonate = e[13].divide(e[14]).rename("raw_carbonate_index")     # Ninomiya CI

    bands = [dem.rename("raw_elevation"), slope, slope_sq, relief, tri, t_min, swing, frost, maat,
             albedo, ati, ndvi, precip, pet, dust, mafic, quartz, carbonate, access]
    if include_s2:  # heaviest layer globally; skip with --no-s2 (Fe-oxide / clay proxies stay NaN)
        s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterDate("2022-01-01", "2023-01-01")
              .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).median())
        bands += [s2.select("B4").divide(s2.select("B2")).rename("raw_fe_ratio"),
                  s2.select("B11").divide(s2.select("B12")).rename("raw_clay_ratio")]
    return ee.Image.cat(bands)


RAW_BANDS = ["raw_elevation", "raw_slope", "raw_slope_sq", "raw_relief_5km", "raw_tri", "raw_temp_min",
             "raw_diurnal_range", "raw_frost_fraction", "raw_mean_lst", "raw_albedo", "raw_ati", "raw_ndvi",
             "raw_precip_mm", "raw_pet_mm", "raw_dust_aod", "raw_mafic_index", "raw_quartz_index",
             "raw_carbonate_index", "raw_access_minutes", "raw_fe_ratio", "raw_clay_ratio"]
MAX_CELLS_PER_TASK = 5000


def land_only(cells: pd.DataFrame) -> pd.DataFrame:
    """Drop open-ocean cells (no country). Antarctica keeps ISO3 'ATA'."""
    return cells[cells["iso3"].notna()].reset_index(drop=True) if "iso3" in cells.columns else cells


def chunks(cells: pd.DataFrame, size: int = MAX_CELLS_PER_TASK):
    for i in range(0, len(cells), size):
        yield i // size, cells.iloc[i:i + size]


def _cells_fc(cells: pd.DataFrame):
    ee = _ee()
    feats = [ee.Feature(ee.Geometry.Rectangle([r.lon - r.half_dlon, r.lat - r.half_dlat,
                                               r.lon + r.half_dlon, r.lat + r.half_dlat]),
                        {"cell_id": r.cell_id})
             for r in cells.itertuples()]
    return ee.FeatureCollection(feats)


def sample_cells(cells: pd.DataFrame, chunk: int = 50, include_s2: bool = True) -> pd.DataFrame:
    """Direct (synchronous) extraction for small areas, e.g. one country or a test bbox.

    Small chunks keep each getInfo() well under Earth Engine's interactive time limit.
    """
    ee = _ee()
    img = raw_stack(include_s2)
    frames = []
    cells = land_only(cells)
    for i in range(0, len(cells), chunk):
        fc = _cells_fc(cells.iloc[i:i + chunk])
        means = img.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=SCALE_M, tileScale=4)
        frames.append(pd.DataFrame([f["properties"] for f in means.getInfo()["features"]]))
        print(f"  sampled {min(i + chunk, len(cells))}/{len(cells)} cells", flush=True)
    raw = pd.concat(frames, ignore_index=True).dropna(subset=["raw_elevation"])   # ocean -> no DEM -> dropped
    return cells.merge(raw, on="cell_id", how="inner")


def export_cells(cells: pd.DataFrame, description: str, folder: str = "analog_atlas", include_s2: bool = True):
    """Asynchronous Drive export for one batch of <= 5000 land cells."""
    ee = _ee()
    if len(cells) > MAX_CELLS_PER_TASK:
        raise ValueError(f"{len(cells)} cells > {MAX_CELLS_PER_TASK} per task; split with chunks() first")
    img = raw_stack(include_s2)
    fc = _cells_fc(cells)
    table = img.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=SCALE_M, tileScale=8)
    cols = [b for b in RAW_BANDS if include_s2 or b not in ("raw_fe_ratio", "raw_clay_ratio")]
    task = ee.batch.Export.table.toDrive(collection=table, description=description, folder=folder,
                                        fileFormat="CSV", selectors=["cell_id", *cols])  # no .geo column
    task.start()
    return task


def merge_exports(csv_paths, grid: pd.DataFrame, fill_dem_project: str | None = None) -> pd.DataFrame:
    """Drive CSV exports -> one frame with lat/lon/iso3 from the grid -> postprocess() features.

    Run on the WHOLE global set at once: ti_rel and dust_activity are percentiles over Earth land.
    """
    parts = [pd.read_csv(p) for p in csv_paths]
    if not parts:
        raise FileNotFoundError("no export CSVs found")
    raw = pd.concat(parts, ignore_index=True).drop(columns=["system:index", ".geo"], errors="ignore")
    raw = raw.drop_duplicates("cell_id", keep="last")
    # Exports hold land cells only, so a missing elevation does NOT mean ocean: NASADEM stops at 60N / 56S,
    # which would silently delete Antarctica and the Arctic (the polar analogs of the lunar south pole).
    # Drop only cells with no measurement at all; fill_dem() can add polar terrain from Copernicus GLO-30.
    meas = [c for c in RAW_BANDS if c in raw.columns]
    raw = raw.dropna(subset=meas, how="all")
    if fill_dem_project and "raw_elevation" in raw and raw["raw_elevation"].isna().any():
        init(fill_dem_project)
        raw = fill_dem(raw, grid)
    keep = [c for c in ("cell_id", "lat", "lon", "iso3") if c in grid.columns]
    return postprocess(grid[keep].merge(raw, on="cell_id", how="inner"))


def fill_dem(raw: pd.DataFrame, grid: pd.DataFrame, chunk: int = 200) -> pd.DataFrame:
    """Fill terrain bands for cells NASADEM does not cover (|lat| beyond 60N / 56S) from Copernicus GLO-30.

    Synchronous sampling; only cells with a missing raw_elevation are queried. Returns raw with the gaps filled.
    """
    ee = _ee()
    col = ee.ImageCollection("COPERNICUS/DEM/GLO30_2024_1").select("DEM")
    dem = col.mosaic().setDefaultProjection(col.first().projection())
    slope = ee.Terrain.slope(dem)
    img = ee.Image.cat([
        dem.rename("raw_elevation"), slope.rename("raw_slope"), slope.multiply(slope).rename("raw_slope_sq"),
        dem.focalMax(2500, "circle", "meters").subtract(dem.focalMin(2500, "circle", "meters")).rename("raw_relief_5km"),
    ])
    todo = raw[raw["raw_elevation"].isna()][["cell_id"]].merge(grid, on="cell_id", how="inner")
    print(f"filling terrain for {len(todo):,} cells outside NASADEM coverage (Copernicus GLO-30)", flush=True)
    filled = []
    for i in range(0, len(todo), chunk):
        fc = _cells_fc(todo.iloc[i:i + chunk])
        res = img.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=SCALE_M, tileScale=4).getInfo()
        filled.append(pd.DataFrame([f["properties"] for f in res["features"]]))
        print(f"  {min(i + chunk, len(todo)):,}/{len(todo):,}", flush=True)
    if not filled:
        return raw
    fill = pd.concat(filled, ignore_index=True).set_index("cell_id")
    out = raw.set_index("cell_id")
    for c in ("raw_elevation", "raw_slope", "raw_slope_sq", "raw_relief_5km"):
        if c in fill:
            out[c] = out[c].fillna(fill[c])
    return out.reset_index()


def _pct_rank(series: pd.Series) -> pd.Series:
    return series.rank(pct=True)


def postprocess(raw: pd.DataFrame) -> pd.DataFrame:
    """Raw GEE columns -> v2 feature columns (see config/features.json for meaning)."""
    f = pd.DataFrame({"cell_id": raw["cell_id"], "lat": raw["lat"], "lon": raw["lon"]})
    if "iso3" in raw:
        f["iso3"] = raw["iso3"]
    clip = lambda s, lo=0.0, hi=1.0: s.clip(lo, hi)  # noqa: E731

    f["slope_mean"] = raw["raw_slope"]
    f["slope_std"] = np.sqrt((raw["raw_slope_sq"] - raw["raw_slope"] ** 2).clip(lower=0))
    # Roughness is NOT taken from raw_tri: the 90 m focal window collapses to ~0 when the stack is reduced at
    # SCALE_M = 1 km (smoke test 2026-11-14: exactly 0 at Kula and Lake Salda). A constant 0 would bias every
    # Earth cell; missing (NaN) lets the scorer skip it and report coverage instead. Recalibrate before reusing.
    f["roughness"] = np.nan
    f["relief_local"] = raw["raw_relief_5km"]
    f["crater_density"] = np.nan                                       # needs impact DB + depression detection

    f["albedo"] = raw["raw_albedo"]
    f["ti_rel"] = _pct_rank(raw["raw_ati"])                            # percentile over Earth land
    f["rock_abundance"] = np.nan                                       # needs SAR / TIR model

    f["temp_min"] = raw["raw_temp_min"]
    f["diurnal_range"] = raw["raw_diurnal_range"]
    f["frost_fraction"] = raw["raw_frost_fraction"]
    f["sun_elev_noon"] = noon_sun_elevation("earth", raw["lat"].to_numpy())

    ratio = raw["raw_precip_mm"] / raw["raw_pet_mm"].where(raw["raw_pet_mm"] > 0)
    f["aridity"] = 1 - clip(ratio.fillna(0))                           # no PET (ice) -> treated as arid
    f["ground_ice"] = clip(-raw["raw_mean_lst"] / 10.0)               # PROXY: MAAT below 0 C -> permafrost

    mafic = clip((raw["raw_mafic_index"] - 0.98) / 0.06)               # PROXY (Ninomiya MI)
    f["mineral_olivine"] = 0.3 * mafic
    f["mineral_pyroxene"] = 0.5 * mafic
    f["mineral_plagioclase"] = np.nan                                  # needs EMIT / unmixing
    f["mineral_evaporite"] = np.nan                                    # needs salt index
    nan = pd.Series(np.nan, index=raw.index)                           # exports run with --no-s2 lack these
    f["mineral_hematite"] = 0.5 * clip((raw.get("raw_fe_ratio", nan) - 1.0) / 1.5)          # PROXY
    f["mineral_phyllosilicate"] = 0.3 * clip((raw.get("raw_clay_ratio", nan) - 1.0) / 0.4)  # PROXY
    f["mineral_carbonate"] = 0.6 * clip((raw["raw_carbonate_index"] - 1.0) / 0.03)  # PROXY (Ninomiya CI)

    f["dust_activity"] = _pct_rank(raw["raw_dust_aod"])
    f["vegetation_cover"] = clip((raw["raw_ndvi"] - 0.05) / 0.75)
    f["cave_index"] = np.nan                                           # needs cave / lava-tube inventory
    f["landform_class"] = None                                         # needs landform classifier
    if "raw_access_minutes" in raw:                                    # not a feature: access-bonus input
        f["access_minutes"] = raw["raw_access_minutes"].to_numpy(float)
    return f
