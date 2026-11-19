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

## Decided approach
- **Main method: optical MNDWI** using Landsat 8 (`LANDSAT/LC08/C02/T1_L2`, 30 m) or Sentinel-2 (`COPERNICUS/S2_SR_HARMONIZED`).
  - "During flood": about 22 Apr 2019. "Normal": a snow-free scene from autumn 2018 or summer 2019.
  - Threshold MNDWI at about 0, or use Otsu (justify the choice in the report).
  - Mask snow (NDSI), clouds, and permanent water (JRC Global Surface Water).
- **Validation: Sentinel-1 SAR change detection** (`COPERNICUS/S1_GRD`, IW, VV/VH), following the UN-SPIDER recommended practice.
  - Pre- and post-flood images from the same orbit track.
  - Apply a speckle filter, compute the post/pre ratio, threshold at about 1.25.
  - Mask permanent water and slope.
- **VIIRS** (500 m to 1 km in GEE): context only, e.g. daily flood evolution. Not the main method, because it is too coarse for area comparison and the 10 m WorldCover overlay.
- **Land cover:** ESA WorldCover 2020, 10 m.
- **AOI:** a subset of the valley, e.g. Fargo to Grand Forks or Grand Forks to Pembina.

## Known pitfalls
- Snow scores high on MNDWI (looks like water). Use dates after the melt or apply a snow mask.
- In SAR, wet snow and river ice appear dark (false flood). Use late-April SAR and a snow-free reference.
- Wind can roughen open floodwater so it appears bright in SAR (missed flood).
- Sentinel-1 revisits over the US in 2019 were sparse. Check scene dates and orbits first.
- Floodwater was receding in late April. Keep the optical and SAR dates as close together as possible, and discuss any gap as a limitation.
- Imagery (about 22 Apr) is roughly 2 weeks after the Fargo crest; the crest had moved north by then. Good point for the Discussion.

## Next steps
1. In GEE, list the available S1 / L8 / S2 scenes for 15 Apr – 5 May 2019 over the AOI (dates, orbits, cloud cover).
2. Write the optical MNDWI script and compute flooded area.
3. Write the Sentinel-1 change detection script and compute flooded area plus an agreement map.
4. Do the WorldCover overlay, per-class area, and bar chart.
5. Compare with CIMSS/NOAA flood products and NWS/USGS gauge data. Write the report.