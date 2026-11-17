"""All-source PM2.5: daily tract NetCDF -> parquet (provenance).

Port of the companion coexposure project's `302_total_pm.py`, which produced
`total_total_pm25_pollution.parquet` (in this repository:
data/pm25/allsource_pm25_tract_daily.parquet).

Input: PM25_daily_CensusTract_2005_2020_WesternUS.nc, an ArcGIS space-time cube of
Swanson et al. (2022) daily 1-km PM2.5 averaged to 2020 census tracts
(variable MEAN_NONE_SPATIAL_NEIGHBORS). The Swanson product ends 2020-12-14.

The pipeline reads only time, location_label and pm25; the flag columns are kept so the
output matches the file used in the analysis. The analysis applies its own >= 35
threshold (load.py).

Usage: python preprocessing/allsource_pm25_to_tract_parquet.py INPUT.nc OUTPUT.parquet
"""
import sys

import numpy as np
import pandas as pd
import xarray as xr


def main(nc_path, out_path):
    cube = xr.open_dataset(nc_path)
    df = (cube[["MEAN_NONE_SPATIAL_NEIGHBORS"]].to_dataframe()
          .rename(columns={"MEAN_NONE_SPATIAL_NEIGHBORS": "pm25"}).reset_index())
    df = df[["time", "locations", "pm25"]]
    df["time"] = pd.to_datetime(df["time"])
    df = df[(df["time"] >= "2006-01-01") & (df["time"] <= "2020-12-31")]

    locs = cube[["location_label"]].to_dataframe()
    df = df.merge(locs, left_on="locations", right_on="labelDim", how="left")
    df = df[["time", "location_label", "pm25"]].groupby(["time", "location_label"]).first().reset_index()

    df["polluted_over_zero"] = np.where(df["pm25"] > 0.0, True, False)
    df["polluted_over_five"] = np.where(df["pm25"] > 5.0, True, False)
    df["polluted_over_35"] = np.where(df["pm25"] >= 35, True, False)
    df.to_parquet(out_path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
