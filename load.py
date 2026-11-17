"""Load inputs and build the tract-level dataset.

Thresholds (inclusive, >=):
  smoke day          wildfire PM2.5   >= 5 ug/m3
  high-pollution day all-source PM2.5 >= 35 ug/m3 (24-hour NAAQS level)
"""
import logging
import os

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from shapely.geometry import Point

import config

log = logging.getLogger(__name__)

STATES = ["AZ", "CA", "CO", "ID", "MT", "NV", "NM", "OR", "UT", "WA", "WY"]
SMOKE_DAY_UGM3 = 5
HIGH_POLLUTION_UGM3 = 35
STUDY_START, STUDY_END = "2006-01-01", "2020-12-31"
CRS = "ESRI:102003"  # USA Contiguous Albers Equal Area
TRACTS_CACHE = os.path.join(config.CACHE_DIR, "tracts.pkl")


# --------------------------------------------------------------------- daily PM2.5 -> tract
def _daily_to_tract(path, tract_col, date_col, value_col, threshold, prefix):
    """Per-tract exposure summaries from a daily tract file, read in batches.

    Returns, for each tract:
      {prefix}_days           days with value >= threshold, 2006-2020
      {prefix}_days_per_year  mean over years of the yearly count
      {prefix}_annual_mean    mean over years of the annual mean concentration
    """
    parts = []
    for batch in pq.ParquetFile(path).iter_batches(columns=[tract_col, date_col, value_col],
                                                   batch_size=5_000_000):
        b = batch.to_pandas()
        b = b[(b[date_col] >= STUDY_START) & (b[date_col] <= STUDY_END)]
        b["year"] = b[date_col].dt.year
        b["exceed"] = b[value_col] >= threshold
        parts.append(b.groupby([tract_col, "year"]).agg(
            exceed=("exceed", "sum"), total=(value_col, "sum"), n=(value_col, "count")))
    yearly = pd.concat(parts).groupby(level=[0, 1]).sum()
    yearly["mean"] = yearly["total"] / yearly["n"]
    by_tract = yearly.groupby(level=0)
    out = pd.DataFrame({
        f"{prefix}_days": by_tract["exceed"].sum(),
        f"{prefix}_days_per_year": by_tract["exceed"].mean(),
        f"{prefix}_annual_mean": by_tract["mean"].mean(),
    })
    out.index.name = "location_label"
    return out


def load_smoke():
    log.info("Aggregating daily wildfire PM2.5 (%s)", config.SMOKE_PM25_PATH)
    return _daily_to_tract(config.SMOKE_PM25_PATH, "FIPS", "date", "weighted_pm",
                           SMOKE_DAY_UGM3, "smoke")


def load_allsource():
    log.info("Aggregating daily all-source PM2.5 (%s)", config.ALLSOURCE_PM25_PATH)
    return _daily_to_tract(config.ALLSOURCE_PM25_PATH, "location_label", "time", "pm25",
                           HIGH_POLLUTION_UGM3, "highpm")


# --------------------------------------------------------------------- census
def load_tract_shapes():
    g = gpd.read_file(config.TRACTS_SHP_PATH)
    g = g[g["STATE_ABBR"].isin(STATES)].to_crs(CRS)
    return g.set_index(g["FIPS"].rename("location_label"))[
        ["STATE_ABBR", "POPULATION", "SQMI", "geometry"]]


def load_urban_rural():
    """2020 Census urban/rural population (NHGIS ds258, table P2): urban if urban > rural."""
    u = pd.read_csv(config.URBAN_RURAL_PATH, dtype={"GEOID": str})
    u.index = u["GEOID"].str.split("US").str[1].rename("location_label")
    return np.where(u["U7I002"] > u["U7I003"], "Urban", "Rural"), u.index


def load_cenpop():
    """Census 2020 tract population and population-weighted centroids, keyed by tract FIPS."""
    c = pd.read_csv(config.CENPOP_PATH, dtype=str, encoding="utf-8-sig")
    c.index = (c.STATEFP + c.COUNTYFP + c.TRACTCE).rename("location_label")
    c[["LATITUDE", "LONGITUDE"]] = c[["LATITUDE", "LONGITUDE"]].astype(float)
    c["POPULATION"] = c["POPULATION"].astype(int)
    return c


def build_tract_dataset(reload=False):
    """One row per study tract, with exposures, urban/rural class, and centroids (cached)."""
    if not reload and os.path.exists(TRACTS_CACHE):
        return pd.read_pickle(TRACTS_CACHE)
    tracts = load_tract_shapes()
    smoke, allsource = load_smoke(), load_allsource()
    classes, idx = load_urban_rural()
    tracts = (tracts.join(smoke).join(allsource)
              .join(pd.Series(classes, index=idx, name="classification")))
    cenpop = load_cenpop()
    tracts = tracts.join(cenpop[["LATITUDE", "LONGITUDE"]])
    assert tracts["LATITUDE"].notna().all(), "tract missing a population-weighted centroid"
    assert tracts["smoke_days"].notna().all(), "tract missing wildfire PM2.5"
    tracts["smoke_pd"] = tracts["POPULATION"] * tracts["smoke_days"]
    tracts["highpm_pd"] = tracts["POPULATION"] * tracts["highpm_days"]

    # provenance for the data notes
    state_fips = cenpop.loc[cenpop.index.isin(tracts.index), "STATEFP"].unique()
    in_states = cenpop[cenpop.STATEFP.isin(state_fips)]
    missing = in_states[~in_states.index.isin(tracts.index)]
    tracts.attrs = {
        "census_tracts_in_states": len(in_states),
        "census_tracts_missing": len(missing),
        "census_residents_missing": int(missing.POPULATION.sum()),
        "smoke_tracts_outside_study_area": sorted(set(smoke.index) - set(tracts.index)),
        "tracts_without_allsource_pm25": int(tracts["highpm_days"].isna().sum()),
    }
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    pd.to_pickle(tracts, TRACTS_CACHE)
    return tracts


# --------------------------------------------------------------------- monitoring sites
def load_monitor_sites(tracts, min_valid_days=1):
    """One row per monitoring site in the study area, flagged regulatory or AQI-only.

    regulatory : parameter 88101 with a NAAQS annual summary ("PM25 Annual 2012")
    AQI-only   : parameter 88502, continuous (1-hour), at a site with no regulatory monitor.
                 These rows have a blank Pollutant Standard because EPA computes NAAQS
                 summaries only for regulatory monitors, so they are selected explicitly.
    A site counts if any of its monitors has >= min_valid_days valid days in the 2025
    file (data through 2025-06-30). Colocated monitors are deduplicated by site ID.
    """
    m = pd.read_csv(config.MONITORS_PATH, low_memory=False)
    m["site_id"] = (m["State Code"].astype(str).str.zfill(2) + "-"
                    + m["County Code"].astype(str).str.zfill(3) + "-"
                    + m["Site Num"].astype(str).str.zfill(4))
    regulatory = m[(m["Parameter Code"] == 88101) & (m["Pollutant Standard"] == "PM25 Annual 2012")]
    continuous = m[(m["Parameter Code"] == 88502) & (m["Sample Duration"] == "1 HOUR")]

    def reporting(df):
        valid_days = df.groupby("site_id")["Valid Day Count"].max()
        return set(valid_days[valid_days >= min_valid_days].index)

    reg_ids = reporting(regulatory)
    aqi_ids = reporting(continuous) - reg_ids
    rows = pd.concat([regulatory[regulatory.site_id.isin(reg_ids)],
                      continuous[continuous.site_id.isin(aqi_ids)]])
    n_monitors = rows.groupby("site_id")[["Parameter Code", "POC"]].apply(
        lambda d: len(d.drop_duplicates())).rename("n_monitors")
    sites = rows.drop_duplicates("site_id")[["site_id", "Latitude", "Longitude"]].join(
        n_monitors, on="site_id")
    sites["regulatory"] = sites.site_id.isin(reg_ids)
    sites["site_type"] = np.where(sites["regulatory"], "regulatory", "AQI-only")

    g = gpd.GeoDataFrame(
        sites, geometry=[Point(xy) for xy in zip(sites.Longitude, sites.Latitude)],
        crs="EPSG:4326").to_crs(CRS)
    g = gpd.sjoin(g, tracts[["geometry", "STATE_ABBR", "classification"]],
                  how="inner", predicate="within").rename(columns={"index_right": "location_label"})
    return g.reset_index(drop=True)
