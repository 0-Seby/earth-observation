"""Shared settings and helpers for the 2019 Red River flood notebooks.

Every notebook does `import common` so all steps use the same dates, AOI,
datasets and thresholds.
"""
import os
from pathlib import Path

import ee
import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "outputs" / "figures"
TABLES = ROOT / "outputs" / "tables"

# --- Dates -----------------------------------------------------------------
FARGO_CREST = "2019-04-08"
GRAND_FORKS_CREST = "2019-04-11"
FLOOD_WINDOW = ("2019-04-12", "2019-05-10")      # search window for "during flood" scenes
REF_WINDOW_AUTUMN = ("2018-09-01", "2018-10-31")  # snow-free reference candidates
REF_WINDOW_SUMMER = ("2019-06-01", "2019-08-31")

# --- Areas of interest (lon_min, lat_min, lon_max, lat_max) -----------------
# Rough boxes around the valley; final choice after the scene-availability check.
AOI_BOXES = {
    "fargo_grandforks": [-97.25, 46.80, -96.60, 47.98],
    "grandforks_pembina": [-97.45, 47.85, -96.85, 49.00],
}


def aoi(name: str = "grandforks_pembina") -> ee.Geometry:
    return ee.Geometry.Rectangle(AOI_BOXES[name])


# --- Earth Engine datasets -------------------------------------------------
LANDSAT8 = "LANDSAT/LC08/C02/T1_L2"
SENTINEL2 = "COPERNICUS/S2_SR_HARMONIZED"
SENTINEL1 = "COPERNICUS/S1_GRD"
JRC_GSW = "JRC/GSW1_4/GlobalSurfaceWater"
WORLDCOVER = "ESA/WorldCover/v100"  # 2020, 10 m
DEM = "USGS/SRTMGL1_003"

# --- Method parameters (to be justified in the report) ---------------------
MNDWI_THRESHOLD = 0.0
SAR_RATIO_THRESHOLD = 1.25
PERMANENT_WATER_OCCURRENCE = 80  # % occurrence in JRC GSW treated as permanent water
MAX_SLOPE_DEG = 5


# --- Helpers ---------------------------------------------------------------
def init() -> None:
    """Initialise Earth Engine with the Cloud project from .env (EE_PROJECT)."""
    load_dotenv(ROOT / ".env")
    project = os.getenv("EE_PROJECT")
    if not project or project == "your-gcp-project-id":
        raise RuntimeError("Set EE_PROJECT in .env (copy .env.example).")
    try:
        ee.Initialize(project=project)
    except ee.EEException as e:
        # Only re-authenticate when credentials are missing/expired; surface
        # other errors (e.g. wrong project or missing IAM permission) as-is.
        if "authenticate" not in str(e).lower() and "authorize" not in str(e).lower():
            raise
        ee.Authenticate()
        ee.Initialize(project=project)


def scene_table(col: ee.ImageCollection, props: dict[str, str]) -> pd.DataFrame:
    """Metadata of every image in `col` as a DataFrame.

    props maps output column name -> image property name. A 'date' column
    (UTC, from system:time_start) is always added.
    """
    def to_feature(img):
        values = {name: img.get(prop) for name, prop in props.items()}
        values["date"] = img.date().format("YYYY-MM-dd HH:mm")
        return ee.Feature(None, values)

    feats = ee.FeatureCollection(col.map(to_feature)).getInfo()["features"]
    df = pd.DataFrame([f["properties"] for f in feats])
    if df.empty:
        return df
    return df[["date", *props]].sort_values("date").reset_index(drop=True)



def Map(center=(47.9, -97.0), zoom=7, **kwargs):
    """geemap.Map with the standard OSM basemap.

    geemap's default basemap (OpenStreetMap.HOT from openstreetmap.fr) does not
    load inside VS Code notebooks, which leaves the whole map blank.
    """
    import geemap
    import ipyleaflet
    kwargs.setdefault("basemap", ipyleaflet.basemaps.OpenStreetMap.Mapnik)
    return geemap.Map(center=list(center), zoom=zoom, **kwargs)
