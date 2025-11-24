import os
from os.path import basename, join
import logging

logging.basicConfig(level = logging.INFO)


WEATHER_PATH = "../coexposure/outputs/final_merge_5_western_us.parquet"
SMOKEPM25_PATH = "smoke_pm/area_weighted_smoke_pm_corr.parquet"
TOTALPM25_PATH = "../coexposure/outputs/total_total_pm25_pollution.parquet"
RURAL_PATH = '../coexposure/data/joan_ruca/ruca2020.csv'
CTSHAPEFILE_PATH = '../coexposure/data/WesternUSCensusTract/CensusTract2020_WesternUS.shp'
MONITORS_PATH = "data/annual_conc_by_monitor_2025.csv" # "../coexposure/data/annual_conc_by_monitor_2023.csv"
STATESHAPEFILE_PATH = '../coexposure/data/usastate/tl_2020_us_state.shp'

map_fig_size = 3,3 

color_palette = "magma_r"
        
    
if __name__ == '__main__':
    for path in [WEATHER_PATH , RURAL_PATH , CTSHAPEFILE_PATH , MONITORS_PATH, STATESHAPEFILE_PATH]:
        print(f"scp afogelson@txe1-login.mit.edu:{path} .")