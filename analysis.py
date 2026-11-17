"""Every number in the EHP letter: distances, shares, Table 1, priority ranking.

Networks
  reg : regulatory sites (parameter 88101)
  all : regulatory + AQI-only sites (88101 + continuous 88502)
Distances are great-circle km from Census 2020 population-weighted tract centroids
to the nearest site.

Non-smoke high-pollution days (high-pollution day: all-source PM2.5 >= 35):
  (a) all-source minus wildfire PM2.5 >= 35
  (b) high-pollution day that is not a smoke day (wildfire PM2.5 < 5)
Tract-days with no wildfire PM2.5 record count as non-smoke (conservative).
"""
import os

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

import config
from load import (HIGH_POLLUTION_UGM3, SMOKE_DAY_UGM3, STUDY_END, STUDY_START,
                  build_tract_dataset, load_monitor_sites)

MIN_VALID_DAYS = 1
DISTANCES_KM = [10, 25, 50]
NETWORKS = {"reg": "Regulatory (88101)", "all": "Regulatory + AQI-only (88101 + 88502)"}
NONSMOKE_CACHE = os.path.join(config.CACHE_DIR, "nonsmoke_days.pkl")
MEASURES = {
    "Smoke person-days": "smoke_pd",
    "Residents": "POPULATION",
    "All high-pollution person-days": "highpm_pd",
    "Non-smoke high-pollution person-days (b)": "nonsmoke_b_pd",
    "Non-smoke high-pollution person-days (a)": "nonsmoke_a_pd",
}


# --------------------------------------------------------------------- build
def nearest_site_km(tracts, sites):
    la1 = np.radians(tracts["LATITUDE"].values)[:, None]
    lo1 = np.radians(tracts["LONGITUDE"].values)[:, None]
    la2 = np.radians(sites["Latitude"].values)[None, :]
    lo2 = np.radians(sites["Longitude"].values)[None, :]
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return (2 * 6371 * np.arcsin(np.sqrt(a))).min(axis=1)


def nonsmoke_highpm_days(tracts, reload=False):
    """Per-tract high-pollution day counts split by smoke contribution (cached)."""
    if not reload and os.path.exists(NONSMOKE_CACHE):
        return pd.read_pickle(NONSMOKE_CACHE)
    hp = pq.read_table(config.ALLSOURCE_PM25_PATH, columns=["time", "location_label", "pm25"],
                       filters=[("pm25", ">=", HIGH_POLLUTION_UGM3)]).to_pandas()
    hp = hp[(hp.time >= STUDY_START) & (hp.time <= STUDY_END)
            & hp.location_label.isin(set(tracts.index))]
    hp = hp.rename(columns={"time": "date", "location_label": "FIPS"})
    keys = hp[["FIPS", "date"]]
    parts = [b.to_pandas().merge(keys, on=["FIPS", "date"], how="inner")
             for b in pq.ParquetFile(config.SMOKE_PM25_PATH).iter_batches(
                 columns=["FIPS", "date", "weighted_pm"], batch_size=5_000_000)]
    hp = hp.merge(pd.concat(parts).drop_duplicates(["FIPS", "date"]), on=["FIPS", "date"], how="left")
    info = {"highpm_tract_days": len(hp), "no_smoke_record": int(hp.weighted_pm.isna().sum())}
    hp["weighted_pm"] = hp["weighted_pm"].fillna(0)  # no smoke record -> non-smoke
    hp["nonsmoke_a"] = (hp.pm25 - hp.weighted_pm) >= HIGH_POLLUTION_UGM3
    hp["nonsmoke_b"] = hp.weighted_pm < SMOKE_DAY_UGM3
    info["smoke_share_of_highpm_days"] = float((~hp["nonsmoke_b"]).mean())
    days = hp.groupby("FIPS").agg(highpm=("pm25", "size"), nonsmoke_a=("nonsmoke_a", "sum"),
                                  nonsmoke_b=("nonsmoke_b", "sum")).reindex(tracts.index).fillna(0)
    assert (days.highpm - tracts.highpm_days.fillna(0)).abs().max() == 0, \
        "high-pollution day counts disagree with load.py"
    out = (days, info)
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    pd.to_pickle(out, NONSMOKE_CACHE)
    return out


def build(reload=False, min_valid_days=MIN_VALID_DAYS):
    """Tract dataset with distances to both networks, priority, and non-smoke person-days."""
    tracts = build_tract_dataset(reload=reload)
    sites = load_monitor_sites(tracts, min_valid_days)
    tracts["dist_reg"] = nearest_site_km(tracts, sites[sites.regulatory])
    tracts["dist_all"] = nearest_site_km(tracts, sites)
    for net in NETWORKS:
        tracts[f"priority_{net}"] = priority(tracts, f"dist_{net}")
    days, info = nonsmoke_highpm_days(tracts, reload=reload)
    for c in ["nonsmoke_a", "nonsmoke_b"]:
        tracts[f"{c}_pd"] = tracts["POPULATION"] * days[c]
    tracts.attrs.update(info)
    return tracts, sites


# --------------------------------------------------------------------- metrics
def share_beyond(tracts, weight_col, dist_col, d):
    """Percent of `weight_col` in tracts farther than d km (d scalar or array)."""
    w = tracts[weight_col].fillna(0).values
    dist = tracts[dist_col].values
    order = np.argsort(dist)
    cum = np.concatenate([[0], np.cumsum(w[order]) / w.sum()])
    idx = np.searchsorted(dist[order], np.atleast_1d(d), side="right")
    out = 100 * (1 - cum[idx])
    return out if np.ndim(d) else out[0]


def priority(tracts, dist_col):
    """Mean annual wildfire PM2.5 x share of regional population x distance (x1e3)."""
    return (tracts["smoke_annual_mean"] * tracts["POPULATION"] / tracts["POPULATION"].sum()
            * tracts[dist_col]) * 1e3


def distance_table(tracts):
    """Share (%) beyond 10/25/50 km for each measure and network, plus smoke ratios."""
    rows = []
    for net, net_name in NETWORKS.items():
        block = []
        for name, col in MEASURES.items():
            block.append({"network": net_name, "measure": name,
                          **{f"beyond_{d}km": share_beyond(tracts, col, f"dist_{net}", d)
                             for d in DISTANCES_KM}})
        smoke = block[0]
        for defn in ["b", "a"]:
            ns = next(r for r in block if r["measure"].endswith(f"({defn})"))
            block.append({"network": net_name, "measure": f"Ratio: smoke / non-smoke ({defn})",
                          **{k: smoke[k] / ns[k] for k in smoke if k.startswith("beyond")}})
        rows += block
    return pd.DataFrame(rows).round(2)


def curve_check(tracts, a="smoke_pd", b="POPULATION", beyond_km=10, plot_max_km=100):
    """Does curve `a` stay above curve `b` beyond `beyond_km`? (percentage points)

    Exact: the curves change only at tract distances. Past the farthest tract both
    curves are 0, so that point is excluded (not a crossing).
    """
    out = {}
    for net in NETWORKS:
        d = np.unique(tracts[f"dist_{net}"].values)
        d = d[(d > beyond_km) & (d < d.max())]
        gap = share_beyond(tracts, a, f"dist_{net}", d) - share_beyond(tracts, b, f"dist_{net}", d)
        i = int(np.argmin(np.where(d <= plot_max_km, gap, np.inf)))
        below = d[gap < 0]
        out[net] = {"min_gap_pp": round(float(gap[i]), 2), "min_gap_at_km": round(float(d[i]), 1),
                    "smoke_below_residents_anywhere": bool(len(below)),
                    "below_range_km": f"{below.min():.1f}-{below.max():.1f}" if len(below) else ""}
    return out


def state_share_beyond(tracts, km=25, weight_col="smoke_pd"):
    """Per state: % of `weight_col` farther than `km` from the nearest site, both networks."""
    out = {}
    for net in NETWORKS:
        far = tracts[weight_col].where(tracts[f"dist_{net}"] > km, 0)
        g = pd.DataFrame({"far": far, "all": tracts[weight_col]}).groupby(tracts["STATE_ABBR"]).sum()
        out[f"smoke_pd_beyond_{km}km_{net}_pct"] = 100 * g["far"] / g["all"]
    return pd.DataFrame(out).rename_axis("state")


def county_names():
    c = pd.read_csv(config.COUNTY_NAMES_PATH, sep="|", dtype=str)
    return dict(zip(c.STATEFP + c.COUNTYFP, c.COUNTYNAME))


def priority_ranking(tracts, net="all"):
    """All tracts ranked by priority score; the top 10 are flagged."""
    names = county_names()
    r = tracts.sort_values(f"priority_{net}", ascending=False)
    out = pd.DataFrame({
        "rank": np.arange(1, len(r) + 1),
        "fips": r.index,
        "state": r["STATE_ABBR"].values,
        "county": [names.get(f[:5], "") for f in r.index],
        "urban_rural": r["classification"].values,
        "residents": r["POPULATION"].astype(int).values,
        "smoke_pm25_annual_mean": r["smoke_annual_mean"].round(3).values,
        "distance_to_nearest_site_km": r[f"dist_{net}"].round(1).values,
        "priority_score_x1e3": r[f"priority_{net}"].round(3).values,
    })
    out["top10"] = out["rank"] <= 10
    return out


def table1(tracts, sites):
    """Table 1 by state and urban/rural, with both networks and RR."""
    g = ["STATE_ABBR", "classification"]
    reg = sites[sites.regulatory]
    t = pd.DataFrame({
        "tracts": tracts.groupby(g).size(),
        "residents_millions": tracts.groupby(g).POPULATION.sum() / 1e6,
        "smoke_days_per_year_tract_mean": tracts.groupby(g).smoke_days_per_year.mean(),
        "smoke_person_days_millions": tracts.groupby(g).smoke_pd.sum() / 1e6,
        "tracts_with_regulatory_site": reg.groupby(g).location_label.nunique(),
        "regulatory_sites": reg.groupby(g).size(),
        "all_sites": sites.groupby(g).size(),
        "tracts_with_any_site": sites.groupby(g).location_label.nunique(),
    })
    counts = ["tracts", "tracts_with_regulatory_site", "regulatory_sites", "all_sites",
              "tracts_with_any_site"]
    t[counts] = t[counts].fillna(0).astype(int)
    u = t.unstack("classification")
    pop_ratio = u["residents_millions"]["Urban"] / u["residents_millions"]["Rural"]
    rr = pd.DataFrame({
        "rr_regulatory": pop_ratio / (u["tracts_with_regulatory_site"]["Urban"]
                                      / u["tracts_with_regulatory_site"]["Rural"]),
        "rr_all_sites": pop_ratio / (u["tracts_with_any_site"]["Urban"]
                                     / u["tracts_with_any_site"]["Rural"]),
    })
    t = (t.join(rr, on="STATE_ABBR").rename_axis(["state", "urban_rural"])
         .join(state_share_beyond(tracts), on="state"))   # state-level columns repeat per row
    return t.round({"residents_millions": 2, "smoke_days_per_year_tract_mean": 1,
                    "smoke_person_days_millions": 1, "rr_regulatory": 2, "rr_all_sites": 2,
                    "smoke_pd_beyond_25km_reg_pct": 1, "smoke_pd_beyond_25km_all_pct": 1})


def summary(tracts, sites):
    """Scalar numbers and data notes, one row per item."""
    a = tracts.attrs
    cc = curve_check(tracts)
    items = {
        "tracts": len(tracts),
        "residents": int(tracts.POPULATION.sum()),
        "regulatory_sites": int(sites.regulatory.sum()),
        "aqi_only_sites": int((~sites.regulatory).sum()),
        "all_sites": len(sites),
        "census_tracts_in_states": a["census_tracts_in_states"],
        "census_tracts_missing_from_shapefile": a["census_tracts_missing"],
        "residents_in_missing_tracts": a["census_residents_missing"],
        "smoke_tracts_excluded_outside_study_area": ";".join(a["smoke_tracts_outside_study_area"]),
        "tracts_without_allsource_pm25": a["tracts_without_allsource_pm25"],
        "highpm_tract_days": a["highpm_tract_days"],
        "highpm_tract_days_no_smoke_record": a["no_smoke_record"],
        "highpm_tract_days_no_smoke_record_pct": round(100 * a["no_smoke_record"] / a["highpm_tract_days"], 2),
        "highpm_tract_days_that_are_smoke_days_pct": round(100 * a["smoke_share_of_highpm_days"], 2),
        "site_rule": f">= {MIN_VALID_DAYS} valid day in AQS 2025 annual file (data through 2025-06-30)",
    }
    frequent = tracts["smoke_days_per_year"] >= 10
    items["residents_ge10_smoke_days_per_year"] = int(tracts.loc[frequent, "POPULATION"].sum())
    for net in NETWORKS:
        far = frequent & (tracts[f"dist_{net}"] > 25)
        n = int(tracts.loc[far, "POPULATION"].sum())
        items[f"residents_ge10_smoke_days_beyond_25km_{net}"] = n
        items[f"residents_ge10_smoke_days_beyond_25km_{net}_pct"] = round(
            100 * n / items["residents_ge10_smoke_days_per_year"], 2)
    for net in NETWORKS:
        for k, v in cc[net].items():
            items[f"curve_check_{net}_{k}"] = v
    return pd.DataFrame({"item": list(items), "value": list(items.values())})


def write_outputs(tracts, sites):
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    files = {
        "distance_table.csv": distance_table(tracts),
        "table1.csv": table1(tracts, sites),
        "priority_tracts.csv": priority_ranking(tracts),
        "summary.csv": summary(tracts, sites),
    }
    for name, df in files.items():
        df.to_csv(os.path.join(config.OUTPUT_DIR, name), index=name == "table1.csv")
    return list(files)
