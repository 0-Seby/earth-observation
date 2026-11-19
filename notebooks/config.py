"""Inputs, method parameters and decisions for the 2019 Red River flood analysis.

Decisions are checked against the scene tables at the end of notebook 01.
"""
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "outputs" / "figures"
TABLES = ROOT / "outputs" / "tables"


# --- Inputs ------------------------------------------------------------------
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


JRC_GSW = "JRC/GSW1_4/GlobalSurfaceWater"
JRC_MONTHLY = "JRC/GSW1_4/MonthlyHistory"  # monthly water maps from all Landsat images (Pekel et al. 2016)
WORLDCOVER = "ESA/WorldCover/v100"  # 2020, 10 m
# WorldCover class values -> names (catalog page, band "Map").
WORLDCOVER_NAMES = {
    10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland", 50: "Built-up",
    60: "Bare / sparse vegetation", 70: "Snow and ice", 80: "Permanent water bodies",
    90: "Herbaceous wetland", 95: "Mangroves", 100: "Moss and lichen",
}
# WorldCover palette (catalog page).
WORLDCOVER_COLORS = {
    10: "#006400", 20: "#ffbb22", 30: "#ffff4c", 40: "#f096ff", 50: "#fa0000",
    60: "#b4b4b4", 70: "#f0f0f0", 80: "#0064c8", 90: "#0096a0", 95: "#00cf75", 100: "#fae6a0",
}
DEM = "USGS/SRTMGL1_003"

# Peak water level ("crest") of the 2019 flood wave at the river gauges (NWS/USGS).
FARGO_PEAK = "2019-04-08"
GRAND_FORKS_PEAK = "2019-04-11"  # gauge just upstream of our study area

# Candidate areas: [lon_min, lat_min, lon_max, lat_max]
AOI_BOXES = {
    "fargo_grandforks": [-97.25, 46.80, -96.60, 47.98],
    "grandforks_pembina": [-97.45, 47.85, -96.85, 49.00],
}

# Search windows for notebook 01. Windows are [start, end), as Earth Engine expects.
FLOOD_WINDOW = ("2019-04-12", "2019-05-10")
REF_WINDOW_AUTUMN = ("2018-09-01", "2018-10-31")
REF_WINDOW_SUMMER = ("2019-06-01", "2019-08-31")


# --- Method parameters -----------------------------------------------------
MNDWI_THRESHOLD = 0.0             # Xu (2006); Otsu on the 22 Apr image gives 0.059 (notebook 02)
SAR_RATIO_THRESHOLD = 1.25        # UN-SPIDER recommended practice
PERMANENT_WATER_OCCURRENCE = 80   # % of time water in JRC GSW -> treated as permanent water
MAX_SLOPE_DEG = 5                 # UN-SPIDER recommended practice


# --- Decisions ---------------------------------------------------------------
# Notebook 01: only clear Landsat 8 flood image is path 31, 22 Apr.
STUDY_AOI = "grandforks_pembina"  # cut to the Landsat footprint, see common.study_area()
L8_PATH = 31
L8_DURING = "2019-04-22"
L8_BEFORE = "2018-09-10"  # 12 Oct 2018 was snow-covered (notebook 02)
L8_AFTER = "2019-08-28"

# Notebook 01: Sentinel-1 orbit 136 on the same day as Landsat 8.
S1_ORBIT = 136
S1_DURING = "2019-04-22"
S1_AFTER = "2019-08-20"
S1_TIMELINE = [S1_DURING, "2019-05-04", "2019-05-16", S1_AFTER]  # all orbit-136 dates we map
# Notebook 03: late-spring 2018 median (snow-free, no flood, small crops).
S1_BEFORE_WINDOW = ("2018-05-09", "2018-06-03")
