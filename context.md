# Project context: 2019 Red River flood (EO Hydrology assignment)

## Assignment
- Course: 102-0675-00L Earth Observation, group project "EO Applications in Hydrology" (groups of 3).
- All analysis must be done in **Google Earth Engine (GEE)**. Include GEE script links in the report.
- Report: max 5 pages, Overleaf template, line numbers, sections Introduction / Methodology / Results / Discussion / Conclusion. Cite all data and literature.
- Due: today (preliminary report). Missing content or placeholder text costs 0.5 from the final grade.
- Tasks:
  1. **Choose event:** must be before 2022 and have had an impact on people. Explain the choice, how data availability was checked (clouds, temporal gaps), and the temporal and geographic scale.
  2. **Map flood extent:** use a water index (the brief hints at NDWI/MNDWI) and compare before vs during the flood. Questions to answer: method choice and its advantages, how the threshold was chosen, limitations, largest flooded area.
  3. **Validate with a second EO system:** compare before / during / after, compare the areas from both methods (areal difference), and compare with official, literature or news maps.
  4. **Land cover:** overlay the flood mask with e.g. ESA WorldCover, compute flooded area per class, make a map and a bar chart, and discuss which classes retain water.

## Chosen event
- **2019 Red River of the North spring snowmelt flood** (ND/MN border, flows north into Manitoba).
- Fargo crest: 8 Apr 2019, 35.03 ft provisional, 19,500 cfs (USGS), about a 25-year recurrence; top-10 flood for Fargo.
- Grand Forks crest: 11 Apr. The crest then moved north towards Pembina/Emerson (mid–late April).
- 50–100 homes cut off north of Fargo, many roads closed, farm fields flooded.
- Complications: river ice and ice jams into mid-April; a blizzard on 10–12 Apr left 4–6" of new snow.
- Reference blog (CIMSS, 22 Apr 2019): https://cimss.ssec.wisc.edu/satellite-blog/archives/33027. It shows a Landsat-8 false color image plus the GOES-16 ABI and Suomi NPP VIIRS flood products (RealEarth). **Landsat-8 had a usable clear scene on 22 Apr 2019.**

## Code
- Python Earth Engine API in Jupyter notebooks (`notebooks/`). All settings, parameters and decisions (with their source) are in `notebooks/config.py` (`import config as cfg`); helper functions only in `notebooks/common.py` (`import common as c`). Notebook 01 ends with a check cell that asserts the chosen dates in config.py meet the criteria. Tables go to `outputs/tables`, figures to `outputs/figures`.
- Notebooks show the final method only; dead ends go in a short markdown note (with numbers for the Discussion), not as code.
- The user is a beginner: keep the code simple and readable, but clean (typed, enums rather than magic strings, no bloat). Pyright should show 0 errors.
- Open question: the brief asks for "GEE script links". We use Python notebooks, so we probably link the repo / notebooks instead. Check with the course.

## Decisions (done in notebook 01)
- **AOI / study area:** the `grandforks_pembina` box cut to the Landsat 8 footprint of 22 Apr (`c.study_area()`, about 4,240 km², Oslo MN ~48.2° N to the Canadian border). Landsat on 22 Apr covers only 0.8 % of the Fargo box, so that box was dropped.
- **Dates:**

  |        | Landsat 8 (path 31) | Sentinel-1 (orbit 136, ascending) |
  |--------|---------------------|-----------------------------------|
  | Before | 2018-09-10          | median of 9 May – 2 Jun 2018      |
  | During | 2019-04-22          | 2019-04-22 (~17 h before Landsat), also 4 and 16 May |
  | After  | 2019-08-28          | 2019-08-20                        |

- 12 Oct 2018 was the first choice for "before", but it is snow-covered (QA flags 92 % snow).
- Sentinel-1 "before" is a spring 2018 median, not 6 Sep 2018: crop growth/harvest between Sept and April/Aug causes false change (Sept before → 1,406 km² flood, and 463 km² even on flood-free 20 Aug). Single spring dates vary a lot (308–754 km²), so we use a median; the window was picked by season (no snow, no flood, small crops), not by agreement with optical.
- Sentinel-2 is not used: the only clear flood dates (13 and 16 Apr) are right after the blizzard, and 28 Apr – 8 May is cloudy.

## Method
- **Main method: optical MNDWI**, Landsat 8 C2 L2 (`LANDSAT/LC08/C02/T1_L2`, 30 m). Done in notebook 02.
  - Clouds, shadows and snow are masked with `QA_PIXEL` bits 1, 3, 4, 5. NDSI can't be used: for Landsat it is the same formula as MNDWI.
  - Threshold 0. Otsu on the flood image gives 0.059, and the water area differs by only 1.7 %.
  - Flood = water during AND NOT water before AND NOT JRC permanent water (occurrence ≥ 80 %).
- **Validation: Sentinel-1 SAR change detection** (`COPERNICUS/S1_GRD`, IW, VV/VH), following the UN-SPIDER recommended practice.
  - VH, orbit 136. Speckle filter: 50 m focal mean. Ratio during/before (dB) > 1.25. Mask JRC permanent water and slope > 5°. Done in notebook 03.
- **VIIRS** (500 m to 1 km in GEE): context only, e.g. daily flood evolution. Not the main method, because it is too coarse for area comparison and the 10 m WorldCover overlay.
- **Land cover:** ESA WorldCover 2020, 10 m.

## Results so far
- MNDWI (notebook 02): **flood ≈ 742 km²** on 22 Apr (17 % of the study area). Water before 22 km², after 24 km², JRC permanent water 9 km². Less than 1 % masked on all dates. Histogram: `outputs/figures/mndwi_histogram.png`. Areas: `outputs/tables/mndwi_areas.csv`.
- SAR (notebook 03): **567 km²** on 22 Apr (−24 % vs optical). Overlap 524 km²: 71 % of the optical flood is confirmed by SAR, and 92 % of the SAR flood is confirmed by optical. SAR timeline 567 → 468 (4 May) → 259 (16 May) → 26 km² (20 Aug); Landsat 28 Aug 3 km². Figure `outputs/figures/flood_area_timeline.png`, tables `optical_vs_sar.csv`, `flood_area_timeline.csv`.
- Official comparison (notebook 03): Global Flood Database ends 2018 (not usable). JRC GSW Monthly History April 2019: 658 km² non-permanent water; 83 % of optical flood confirmed, 93 % of JRC found by optical (SAR: 81 % / 69 %). NOAA GOES-16 ABI flood product (CIMSS blog, Bachmeier 2019): qualitative, same band Oslo–Grafton/Stephen, >80 % flood fraction.
- Timing: Oslo gauge 37.5 ft on 22 Apr (major stage 36 ft, record 38.4 ft; hydrograph in CIMSS blog) → our images are near the local peak, not two weeks after it (that only holds for Fargo). The flood continues east of the Landsat edge, so 742 km² is a lower bound.
- Land cover (notebook 04, WorldCover 2020, 10 m): optical flood = cropland 624 km² (84 %), grassland 86 (12 %), tree cover 16 (2 %), built-up 1 km². Retention (SAR, share of class flooded 22 Apr → 4 May → 16 May): cropland 15.3 → 13.5 → 8.4 %, grassland 12.4 → 9.0 → 1.7 %, built-up 7.2 → 2.1 → 1.1 %. Cropland keeps water longest. Tree cover: optical 13 % vs SAR 0.8 % (leaf-off trees: optical sees the water, radar gets double bounce → missed). Figures `flooded_landcover_bar.png`, `flooded_landcover_timeline.png`.

## Known pitfalls
- Snow scores high on MNDWI (looks like water). Use dates after the melt and the QA snow mask.
- In SAR, wet snow and river ice appear dark (false flood). Use late-April SAR and a snow-free reference.
- Wind can roughen open floodwater so it appears bright in SAR (missed flood).
- Sentinel-1 revisits over the US in 2019 were sparse. Check scene dates and orbits first.
- Floodwater was receding in late April. Keep the optical and SAR dates as close together as possible, and discuss any gap as a limitation.
- Imagery (22 Apr) is 2 weeks after the Fargo crest, but near the peak at Oslo inside the study area (see Results).

## Next steps
1. ~~Scene availability~~ (notebook 01, done).
2. ~~Optical MNDWI flood map and area~~ (notebook 02, done).
3. ~~Sentinel-1 validation~~ (notebook 03, done). Still missing for Task 3: comparison with official/news maps (CIMSS/NOAA VIIRS flood product).
4. ~~WorldCover overlay~~ (notebook 04, done).
5. ~~Static figures~~ (every notebook saves PNGs to outputs/figures). ~~Official comparison~~ (JRC + GOES-16, notebook 03).
6. Code links: plan is a GitHub link per notebook (not Colab, not PDF appendix); user has not approved pushing yet.
7. Write the report.