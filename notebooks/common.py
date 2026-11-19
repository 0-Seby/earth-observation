"""Helper functions for the 2019 Red River flood notebooks.

All settings (dates, thresholds, datasets, decisions) live in config.py.
"""
import io
import math
import os
import urllib.request
from datetime import date, timedelta
from typing import Any

import ee
import geemap
import ipyleaflet
import matplotlib.image
import numpy as np
from matplotlib.axes import Axes
from matplotlib.patches import Patch
import pandas as pd
from dotenv import load_dotenv

import config as cfg


def get_aoi(name: str = cfg.STUDY_AOI) -> ee.Geometry:
    return ee.Geometry.Rectangle(cfg.AOI_BOXES[name])


def init() -> None:
    """Initialise Earth Engine with the Cloud project from .env (EE_PROJECT)."""
    load_dotenv(cfg.ROOT / ".env")
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


def find_images(sensor: cfg.Sensor, aoi: ee.Geometry, window: tuple[str, str]) -> ee.ImageCollection:
    """All images of `sensor` that touch `aoi` within `window`."""
    images = ee.ImageCollection(sensor.collection_id).filterBounds(aoi).filterDate(*window)
    if sensor is cfg.Sensor.S1:
        # IW mode, dual polarisation
        images = images.filter(ee.Filter.And(
            ee.Filter.eq("instrumentMode", "IW"),
            ee.Filter.listContains("transmitterReceiverPolarisation", "VV"),
            ee.Filter.listContains("transmitterReceiverPolarisation", "VH"),
        ))
    return images


def scenes_per_day(sensor: cfg.Sensor, aoi: ee.Geometry, window: tuple[str, str]) -> pd.DataFrame:
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


def one_day(day: str) -> tuple[str, str]:
    """Date window covering only `day`, e.g. ("2019-04-22", "2019-04-23")."""
    next_day = date.fromisoformat(day) + timedelta(days=1)
    return day, next_day.isoformat()


def landsat8_day(day: str) -> ee.ImageCollection:
    """Landsat 8 images of path cfg.L8_PATH over the valley on `day` (one per WRS row)."""
    images = find_images(cfg.Sensor.L8, get_aoi(), one_day(day))
    return images.filter(ee.Filter.eq("WRS_PATH", cfg.L8_PATH))


def study_area() -> ee.Geometry:
    """The STUDY_AOI box, cut to the Landsat 8 footprint on the flood date."""
    footprint = landsat8_day(cfg.L8_DURING).geometry().dissolve(maxError=100)
    return footprint.intersection(get_aoi(), maxError=100)


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


def optical_water(day: str, aoi: ee.Geometry) -> ee.Image:
    """1 where the Landsat 8 MNDWI on `day` is above cfg.MNDWI_THRESHOLD."""
    return mndwi(landsat8_image(day, aoi)).gt(cfg.MNDWI_THRESHOLD)


def optical_flood(day: str, aoi: ee.Geometry) -> ee.Image:
    """Water on `day` that was not water on the before date and is not permanent water."""
    before = optical_water(cfg.L8_BEFORE, aoi)
    return optical_water(day, aoi).And(before.Not()).And(permanent_water().Not())


def sentinel1_vh_median(window: tuple[str, str], aoi: ee.Geometry) -> ee.Image:
    """Median VH backscatter (dB) of the cfg.S1_ORBIT images in `window`, speckle-filtered.

    For a single day the median just mosaics that day's frames. Speckle filter: 50 m focal mean.
    """
    images = find_images(cfg.Sensor.S1, get_aoi(), window)
    images = images.filter(ee.Filter.eq("relativeOrbitNumber_start", cfg.S1_ORBIT)).select("VH")
    return images.median().clip(aoi).focal_mean(50, "circle", "meters")


def sar_flood(during: ee.Image, before: ee.Image) -> ee.Image:
    """Change-detection flood mask: during/before ratio of the dB values above SAR_RATIO_THRESHOLD
    (darker), without permanent water and steep slopes (UN-SPIDER recommended practice)."""
    ratio = during.divide(before)
    slope = ee.Terrain.slope(ee.Image(cfg.DEM))
    flood = ratio.gt(cfg.SAR_RATIO_THRESHOLD)
    return flood.And(permanent_water().Not()).And(slope.lt(cfg.MAX_SLOPE_DEG))


def permanent_water() -> ee.Image:
    """1 where JRC Global Surface Water saw water at least cfg.PERMANENT_WATER_OCCURRENCE % of the time."""
    occurrence = ee.Image(cfg.JRC_GSW).select("occurrence").unmask(0)
    return occurrence.gte(cfg.PERMANENT_WATER_OCCURRENCE)


def geometry_km2(geometry: ee.Geometry) -> float:
    """Area of a polygon in km²."""
    area_m2 = geometry.area(maxError=1).getInfo()
    if area_m2 is None:
        raise RuntimeError("Earth Engine returned no result.")
    return area_m2 / 1e6


def area_km2(mask: ee.Image, aoi: ee.Geometry, scale: int = 30) -> float:
    """Area in km² of the pixels where `mask` is 1."""
    pixel_km2 = ee.Image.pixelArea().divide(1e6).updateMask(mask)
    result = pixel_km2.reduceRegion(ee.Reducer.sum(), aoi, scale, maxPixels=int(1e10)).getInfo()
    if result is None:
        raise RuntimeError("Earth Engine returned no result.")
    return result["area"]


def area_per_class(mask: ee.Image, classes: ee.Image, aoi: ee.Geometry, scale: int = 10) -> dict[int, float]:
    """Area in km² of the pixels where `mask` is 1, split by the class values in `classes`."""
    # Band 0 = pixel area, band 1 = class. The grouped reducer sums band 0 per value of band 1.
    image = ee.Image.pixelArea().divide(1e6).updateMask(mask).addBands(classes)
    reducer = ee.Reducer.sum().group(groupField=1, groupName="class")
    result = image.reduceRegion(reducer, aoi, scale, maxPixels=int(1e10)).getInfo()
    if result is None:
        raise RuntimeError("Earth Engine returned no result.")
    return {group["class"]: group["sum"] for group in result["groups"]}


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
    """Otsu threshold: histogram split with the largest between-class variance."""
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


# --- Static maps -------------------------------------------------------------
def outline(geometry: ee.Geometry, color: str = "red", width: int = 2) -> ee.Image:
    """The border of `geometry` as an RGB image, to put on top of other layers."""
    border = ee.Image().byte().paint(ee.FeatureCollection(geometry), 1, width)
    return border.visualize(palette=[color])


def download_rgb(image: ee.Image, region: ee.Geometry, width: int = 1000) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Download a visualised (RGB) image as an array, plus its extent (west, east, south, north).

    `image` must already be RGB, e.g. made with image.visualize(...).
    """
    box = region.bounds(maxError=1)
    corners = box.coordinates().getInfo()
    if corners is None:
        raise RuntimeError("Earth Engine returned no result.")
    lons = [lon for lon, lat in corners[0]]
    lats = [lat for lon, lat in corners[0]]
    url = image.getThumbURL({"region": box, "dimensions": width, "format": "png", "crs": "EPSG:4326"})
    with urllib.request.urlopen(url) as response:
        array = matplotlib.image.imread(io.BytesIO(response.read()), format="png")
    return array, (min(lons), max(lons), min(lats), max(lats))


def plot_map(ax: Axes, image: ee.Image, region: ee.Geometry, title: str, width: int = 1000) -> None:
    """Draw a visualised Earth Engine image on a matplotlib axis with lon/lat axes."""
    array, extent = download_rgb(image, region, width)
    ax.imshow(array, extent=extent)
    # equal distances in x and y at the mid latitude
    mid_lat = (extent[2] + extent[3]) / 2
    ax.set_aspect(1 / math.cos(math.radians(mid_lat)))
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("Longitude (°)")
    ax.set_ylabel("Latitude (°)")


def legend_patches(colors: dict[str, str]) -> list[Patch]:
    """Legend entries (coloured squares) from {label: colour}."""
    return [Patch(facecolor=color, edgecolor="grey", label=label) for label, color in colors.items()]


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
