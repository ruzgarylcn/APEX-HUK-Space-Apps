"""Earth feature extraction with Google Earth Engine (NASA datasets hosted on GEE).

STATUS: written against the public GEE catalog but NOT yet run (needs `pip install
earthengine-api` and `earthengine authenticate` with a GEE-enabled Google Cloud project).

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


def raw_stack():
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
    maat = day.merge(night).mean().rename("raw_mean_lst")

    albedo = (ee.ImageCollection("MODIS/061/MCD43A3").filterDate(start, end)
              .select("Albedo_WSA_shortwave").median().multiply(0.001).rename("raw_albedo"))
    # Apparent thermal inertia ATI = (1 - albedo) / (Tday - Tnight); percentile taken in postprocess.
    ati = ee.Image(1).subtract(albedo).divide(swing.max(1)).rename("raw_ati")

    ndvi = (ee.ImageCollection("MODIS/061/MOD13A2").filterDate(start, end)
            .select("NDVI").median().multiply(0.0001).rename("raw_ndvi"))

    precip = (ee.ImageCollection("NASA/GPM_L3/IMERG_MONTHLY_V07").filterDate(start, end)
              .select("precipitation").mean().multiply(24 * 365.25).rename("raw_precip_mm"))
    pet = (ee.ImageCollection("MODIS/061/MOD16A2").filterDate(start, end)
           .select("PET").mean().multiply(0.1 * 46).rename("raw_pet_mm"))

    dust = (ee.ImageCollection("NASA/GSFC/MERRA/aer/2").filterDate("2022-01-01", "2023-01-01")
            .select("DUEXTTAU").mean().rename("raw_dust_aod"))

    aster = ee.Image("NASA/ASTER_GED/AG100_003")
    e = {b: aster.select(f"emissivity_band{b}").multiply(0.001) for b in (10, 11, 12, 13, 14)}
    mafic = e[12].divide(e[13]).rename("raw_mafic_index")             # Ninomiya MI
    quartz = e[11].multiply(e[11]).divide(e[10].multiply(e[12])).rename("raw_quartz_index")
    carbonate = e[13].divide(e[14]).rename("raw_carbonate_index")     # Ninomiya CI

    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterDate("2022-01-01", "2023-01-01")
          .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).median())
    fe_ratio = s2.select("B4").divide(s2.select("B2")).rename("raw_fe_ratio")
    clay_ratio = s2.select("B11").divide(s2.select("B12")).rename("raw_clay_ratio")

    return ee.Image.cat([dem.rename("raw_elevation"), slope, slope_sq, relief, tri, t_min, swing, frost, maat,
                         albedo, ati, ndvi, precip, pet, dust, mafic, quartz, carbonate, fe_ratio, clay_ratio])


def _cells_fc(cells: pd.DataFrame):
    ee = _ee()
    feats = [ee.Feature(ee.Geometry.Rectangle([r.lon - r.half_dlon, r.lat - r.half_dlat,
                                               r.lon + r.half_dlon, r.lat + r.half_dlat]),
                        {"cell_id": r.cell_id})
             for r in cells.itertuples()]
    return ee.FeatureCollection(feats)


def sample_cells(cells: pd.DataFrame, chunk: int = 500) -> pd.DataFrame:
    """Direct (synchronous) extraction for small areas, e.g. one country or a test bbox."""
    ee = _ee()
    img = raw_stack()
    frames = []
    for i in range(0, len(cells), chunk):
        fc = _cells_fc(cells.iloc[i:i + chunk])
        means = img.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=SCALE_M, tileScale=4)
        frames.append(pd.DataFrame([f["properties"] for f in means.getInfo()["features"]]))
    raw = pd.concat(frames, ignore_index=True).dropna(subset=["raw_elevation"])   # ocean -> no DEM -> dropped
    return cells.merge(raw, on="cell_id", how="inner")


def export_cells(cells: pd.DataFrame, description: str, folder: str = "analog_atlas"):
    """Asynchronous Drive export for large batches (run once per tile of the global grid)."""
    ee = _ee()
    img = raw_stack()
    fc = _cells_fc(cells)
    table = img.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=SCALE_M, tileScale=8)
    task = ee.batch.Export.table.toDrive(collection=table, description=description,
                                        folder=folder, fileFormat="CSV")
    task.start()
    return task


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
    f["roughness"] = clip(raw["raw_tri"] / 30.0)                       # 30 m mean |z - local mean| -> 1
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
    f["mineral_hematite"] = 0.5 * clip((raw["raw_fe_ratio"] - 1.0) / 1.5)          # PROXY
    f["mineral_phyllosilicate"] = 0.3 * clip((raw["raw_clay_ratio"] - 1.0) / 0.4)  # PROXY
    f["mineral_carbonate"] = 0.6 * clip((raw["raw_carbonate_index"] - 1.0) / 0.03)  # PROXY (Ninomiya CI)

    f["dust_activity"] = _pct_rank(raw["raw_dust_aod"])
    f["vegetation_cover"] = clip((raw["raw_ndvi"] - 0.05) / 0.75)
    f["cave_index"] = np.nan                                           # needs cave / lava-tube inventory
    f["landform_class"] = None                                         # needs landform classifier
    return f
