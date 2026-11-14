"""Near-equal-area global grid (no H3 dependency).

Latitude bands of fixed height; inside each band the longitude step widens by 1/cos(lat)
so every cell covers about the same area. ~10 km cells -> ~1.5 M cells over land after
the land mask (applied during extraction: cells with no DEM data are dropped).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0


def build_grid(cell_km: float = 10.0, bbox: tuple[float, float, float, float] | None = None) -> pd.DataFrame:
    """Return cell_id, lat, lon (centers), half sizes and area for a global or bbox grid.

    bbox = (west, south, east, north) in degrees. Polar caps beyond ±85° are skipped
    (Antarctic interior is covered by its own 85° band edge; refine later if needed).
    """
    west, south, east, north = bbox or (-180.0, -85.0, 180.0, 85.0)
    dlat = math.degrees(cell_km / EARTH_RADIUS_KM)
    rows = []
    lat = south + dlat / 2
    band = 0
    while lat < north:
        dlon = min(360.0, dlat / max(math.cos(math.radians(lat)), 1e-6))
        lons = np.arange(west + dlon / 2, east, dlon)
        for j, lon in enumerate(lons):
            rows.append((f"{band:05d}_{j:05d}", lat, lon, dlat / 2, dlon / 2))
        lat += dlat
        band += 1
    frame = pd.DataFrame(rows, columns=["cell_id", "lat", "lon", "half_dlat", "half_dlon"])
    frame["area_km2"] = cell_km * cell_km
    return frame
