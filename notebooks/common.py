"""Shared settings and helpers for the 2019 Red River flood notebooks.

Every notebook does `import common as c` so all steps use the same dates,
AOIs, datasets and thresholds.
"""
import os
from enum import Enum
from pathlib import Path
from typing import Any

import ee
import geemap
import ipyleaflet
import numpy as np
import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "outputs" / "figures"
TABLES = ROOT / "outputs" / "tables"

# --- Dates (windows are [start, end) as Earth Engine expects) ---------------
FARGO_CREST = "2019-04-08"
GRAND_FORKS_CREST = "2019-04-11"
FLOOD_WINDOW = ("2019-04-12", "2019-05-10")
REF_WINDOW_AUTUMN = ("2018-09-01", "2018-10-31")
REF_WINDOW_SUMMER = ("2019-06-01", "2019-08-31")

# --- Areas of interest: [lon_min, lat_min, lon_max, lat_max] ----------------
AOI_BOXES = {
    "fargo_grandforks": [-97.25, 46.80, -96.60, 47.98],
    "grandforks_pembina": [-97.45, 47.85, -96.85, 49.00],
}


def get_aoi(name: str = "grandforks_pembina") -> ee.Geometry:
    return ee.Geometry.Rectangle(AOI_BOXES[name])


# --- Sensors -----------------------------------------------------------------
class Sensor(Enum):
    """Satellite collections and the image properties we read from them.

    Property names come from the "Image Properties" tab of each dataset in the
    Earth Engine catalog (https://developers.google.com/earth-engine/datasets).
    Sentinel-1 is radar, so it has no cloud cover.
    """

    #    collection id                  orbit property               cloud property
    L8 = ("LANDSAT/LC08/C02/T1_L2",      "WRS_PATH",                  "CLOUD_COVER")
    S2 = ("COPERNICUS/S2_SR_HARMONIZED", "SENSING_ORBIT_NUMBER",      "CLOUDY_PIXEL_PERCENTAGE")
    S1 = ("COPERNICUS/S1_GRD",           "relativeOrbitNumber_start", None)

    def __init__(self, collection_id: str, orbit_property: str, cloud_property: str | None) -> None:
        self.collection_id = collection_id
        self.orbit_property = orbit_property
        self.cloud_property = cloud_property


# --- Chosen scenes (see notebook 01) -----------------------------------------
L8_PATH = 31
L8_DATES = {"before": "2018-09-10", "during": "2019-04-22", "after": "2019-08-28"}
S1_ORBIT = 136
S1_DATES = {"before": "2018-09-06", "during": "2019-04-22", "after": "2019-08-20"}

# --- Other datasets ----------------------------------------------------------
JRC_GSW = "JRC/GSW1_4/GlobalSurfaceWater"
WORLDCOVER = "ESA/WorldCover/v100"  # 2020, 10 m
DEM = "USGS/SRTMGL1_003"

# --- Method parameters (to be justified in the report) ---------------------
MNDWI_THRESHOLD = 0.0  # Otsu on the 22 Apr image gives 0.059, see notebook 02
SAR_RATIO_THRESHOLD = 1.25
PERMANENT_WATER_OCCURRENCE = 80  # % occurrence in JRC GSW treated as permanent water
MAX_SLOPE_DEG = 5


def init() -> None:
    """Initialise Earth Engine with the Cloud project from .env (EE_PROJECT)."""
    load_dotenv(ROOT / ".env")
    project = os.getenv("EE_PROJECT")
    if not project or project == "your-gcp-project-id":
        raise RuntimeError("Set EE_PROJECT in .env (copy .env.example).")
    try:
        ee.Initialize(project=project)
    except ee.EEException as error:
        # Re-authenticate only for missing/expired credentials.
        message = str(error).lower()
        if "authenticate" not in message and "authorize" not in message:
            raise
        ee.Authenticate()
        ee.Initialize(project=project)


def find_images(sensor: Sensor, aoi: ee.Geometry, window: tuple[str, str]) -> ee.ImageCollection:
    """All images of `sensor` that touch `aoi` within `window`."""
    images = ee.ImageCollection(sensor.collection_id).filterBounds(aoi).filterDate(*window)
    if sensor is Sensor.S1:
        # IW (Interferometric Wide swath) is the standard Sentinel-1 mode over land;
        # we need both VV and VH polarisations.
        images = images.filter(ee.Filter.And(
            ee.Filter.eq("instrumentMode", "IW"),
            ee.Filter.listContains("transmitterReceiverPolarisation", "VV"),
            ee.Filter.listContains("transmitterReceiverPolarisation", "VH"),
        ))
    return images


def scenes_per_day(sensor: Sensor, aoi: ee.Geometry, window: tuple[str, str]) -> pd.DataFrame:
    """One row per acquisition day: orbit, image count, AOI coverage and scene cloud cover.

    One overpass is split into several images (Landsat rows, S2 tiles, S1
    frames), so images are grouped by day. `aoi_cover_%` is the share of the
    AOI inside that day's footprints; `cloud_%` is the mean over whole scenes.
    """
    def add_day(image: ee.Image) -> ee.Image:
        return ee.Image(image.set("day", image.date().format("YYYY-MM-dd")))

    images = find_images(sensor, aoi, window).map(add_day)
    aoi_area = aoi.area(maxError=100)

    def summarise_day(day: Any) -> ee.Feature:
        same_day = images.filter(ee.Filter.eq("day", day))
        # dissolve() merges overlapping footprints so overlap isn't counted twice.
        footprint = same_day.geometry().dissolve(maxError=100)
        covered = footprint.intersection(aoi, maxError=100).area(maxError=100)
        row = {
            "date": day,
            "orbit": same_day.first().get(sensor.orbit_property),
            "n_images": same_day.size(),
            "aoi_cover_%": covered.divide(aoi_area).multiply(100),
        }
        if sensor.cloud_property:
            row["cloud_%"] = same_day.aggregate_mean(sensor.cloud_property)
        return ee.Feature(None, row)

    days = images.aggregate_array("day").distinct()
    result = ee.FeatureCollection(days.map(summarise_day)).getInfo()
    if result is None:
        raise RuntimeError("Earth Engine returned no result.")

    table = pd.DataFrame([feature["properties"] for feature in result["features"]])
    if table.empty:
        return table
    columns = ["date", "orbit", "n_images", "aoi_cover_%"]
    if sensor.cloud_property:
        columns.append("cloud_%")
    return table.loc[:, columns].sort_values(by="date").round(1).reset_index(drop=True)


def landsat8_day(day: str) -> ee.ImageCollection:
    """Landsat 8 images of path L8_PATH over the valley on `day` (one per WRS row)."""
    start = ee.Date(day)
    return (
        ee.ImageCollection(Sensor.L8.collection_id)
        .filterBounds(get_aoi("grandforks_pembina"))
        .filterDate(start, start.advance(1, "day"))
        .filter(ee.Filter.eq("WRS_PATH", L8_PATH))
    )


def study_area() -> ee.Geometry:
    """The grandforks_pembina box, cut to the Landsat 8 footprint on the flood date."""
    footprint = landsat8_day(L8_DATES["during"]).geometry().dissolve(maxError=100)
    return footprint.intersection(get_aoi("grandforks_pembina"), maxError=100)


# QA_PIXEL bits (see band QA_PIXEL in the catalog): 1 dilated cloud, 3 cloud,
# 4 cloud shadow, 5 snow. A pixel is usable if none of these bits is set.
L8_UNUSABLE_BITS = (1 << 1) | (1 << 3) | (1 << 4) | (1 << 5)


def landsat8_image(day: str, aoi: ee.Geometry) -> ee.Image:
    """Surface reflectance (0-1) on `day`, with cloud, shadow and snow masked."""
    image = landsat8_day(day).mosaic().clip(aoi)
    usable = image.select("QA_PIXEL").bitwiseAnd(L8_UNUSABLE_BITS).eq(0)
    # Collection 2 scale factors, see the catalog page.
    reflectance = image.select("SR_B[1-7]").multiply(0.0000275).add(-0.2)
    return reflectance.updateMask(usable)


def mndwi(image: ee.Image) -> ee.Image:
    """MNDWI = (green - SWIR1) / (green + SWIR1). Landsat 8: green = B3, SWIR1 = B6."""
    return image.normalizedDifference(["SR_B3", "SR_B6"]).rename("mndwi")


def permanent_water() -> ee.Image:
    """1 where JRC Global Surface Water saw water at least PERMANENT_WATER_OCCURRENCE % of the time."""
    occurrence = ee.Image(JRC_GSW).select("occurrence").unmask(0)
    return occurrence.gte(PERMANENT_WATER_OCCURRENCE)


def area_km2(mask: ee.Image, aoi: ee.Geometry, scale: int = 30) -> float:
    """Area in km² of the pixels where `mask` is 1."""
    pixel_km2 = ee.Image.pixelArea().divide(1e6).updateMask(mask)
    result = pixel_km2.reduceRegion(ee.Reducer.sum(), aoi, scale, maxPixels=int(1e10)).getInfo()
    if result is None:
        raise RuntimeError("Earth Engine returned no result.")
    return result["area"]


def histogram(image: ee.Image, aoi: ee.Geometry, scale: int = 30) -> tuple[np.ndarray, np.ndarray]:
    """Histogram of a one-band image: (bin centres, pixel counts)."""
    result = image.reduceRegion(
        ee.Reducer.histogram(maxBuckets=256), aoi, scale, maxPixels=int(1e10)
    ).getInfo()
    if result is None:
        raise RuntimeError("Earth Engine returned no result.")
    hist = next(iter(result.values()))
    return np.array(hist["bucketMeans"]), np.array(hist["histogram"])


def otsu(values: np.ndarray, counts: np.ndarray) -> float:
    """Otsu threshold: the split that best separates the histogram into two classes.

    For every possible split it compares the two class means, weighted by
    class size (between-class variance), and keeps the best split.
    """
    best_score, best_threshold = -1.0, float(values[0])
    for i in range(1, len(values)):
        n_low, n_high = counts[:i].sum(), counts[i:].sum()
        if n_low == 0 or n_high == 0:
            continue
        mean_low = (counts[:i] * values[:i]).sum() / n_low
        mean_high = (counts[i:] * values[i:]).sum() / n_high
        score = n_low * n_high * (mean_low - mean_high) ** 2
        if score > best_score:
            best_score, best_threshold = score, float(values[i])
    return best_threshold


def Map(center: tuple[float, float] = (47.9, -97.0), zoom: int = 7, **kwargs: Any) -> geemap.Map:
    """geemap.Map with the standard OSM basemap.

    geemap's default basemap (OpenStreetMap.HOT) does not load in VS Code
    notebooks, which leaves the whole map blank.
    """
    osm = ipyleaflet.TileLayer(
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution="OpenStreetMap contributors",
        name="OpenStreetMap",
    )
    return geemap.Map(center=list(center), zoom=zoom, basemap=osm, **kwargs)
