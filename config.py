"""Input and output locations.

All inputs live under one data directory (default: ./data). Point the
WFM_DATA_DIR environment variable elsewhere to use a different copy; see
download_data.py for the expected layout and where each file comes from.
"""
import logging
import os
from os.path import join

logging.basicConfig(level=logging.INFO, format="%(message)s")

DATA_DIR = os.environ.get("WFM_DATA_DIR", "data")
CACHE_DIR = os.environ.get("WFM_CACHE_DIR", "cache")
OUTPUT_DIR = "outputs"
FIGURE_DIR = "figures"

# Daily tract-level PM2.5 (2006-2020)
SMOKE_PM25_PATH = join(DATA_DIR, "pm25", "smoke_pm25_tract_daily.parquet")          # Childs et al.
ALLSOURCE_PM25_PATH = join(DATA_DIR, "pm25", "allsource_pm25_tract_daily.parquet")  # Swanson et al.

# Census geography and population
TRACTS_SHP_PATH = join(DATA_DIR, "tracts", "CensusTract2020_WesternUS.shp")
URBAN_RURAL_PATH = join(DATA_DIR, "census", "nhgis_ds258_2020_tract_urban_rural.csv")
CENPOP_PATH = join(DATA_DIR, "census", "CenPop2020_Mean_TR.txt")
COUNTY_NAMES_PATH = join(DATA_DIR, "census", "national_county2020.txt")
STATES_SHP_PATH = join(DATA_DIR, "census", "tl_2020_us_state.shp")

# US EPA AQS annual summary, 2025 snapshot (data through 2025-06-30)
MONITORS_PATH = join(DATA_DIR, "aqs", "annual_conc_by_monitor_2025.csv")
