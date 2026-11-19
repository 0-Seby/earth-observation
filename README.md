# 2019 Red River flood: EO Hydrology project

Flood mapping of the 2019 Red River of the North spring flood with Google Earth Engine
(Python API, Jupyter notebooks). Background and decisions: [context.md](context.md).

## Setup
```fish
python3 -m venv .venv
source .venv/bin/activate.fish
pip install -r requirements.txt
cp .env.example .env            # put your GEE-registered Cloud project ID in it
earthengine authenticate        # one time, opens a browser
jupyter lab                     # kernel: "Python (redriver)"
```

## Layout
- `notebooks/common.py`: shared dates, AOIs, dataset IDs, thresholds and helpers (`import common as c`)
- `notebooks/01_scene_availability.ipynb`: Task 1, scene/date/orbit inventory
- `notebooks/02_mndwi.ipynb`: Task 2, optical flood extent *(next)*
- `notebooks/03_sar.ipynb`: Task 3, Sentinel-1 validation *(next)*
- `notebooks/04_landcover.ipynb`: Task 4, WorldCover overlay *(next)*
- `outputs/figures`, `outputs/tables`: results for the report
- `literature/`: papers and guides
