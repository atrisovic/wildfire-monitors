# Wildfire smoke and the US EPA PM2.5 monitoring network

Code accompanying an EHP research letter on where wildfire smoke exposure occurs relative to
the US Environmental Protection Agency (USEPA) PM2.5 monitoring network in 11 western US states.
For 18,107 census tracts (76.3 million residents), it combines daily tract-level wildfire smoke
PM2.5 and all-source PM2.5 for 2006–2020 with the 2025 monitoring network, and measures how much
smoke exposure, high-pollution exposure, and population lies far from the nearest monitoring
site. It also ranks tracts by monitoring priority and compares urban and rural coverage by state.

**Citation.** TODO-AUTHORS. TODO-PAPER-TITLE. *Environmental Health Perspectives* (submitted).
See `CITATION.cff`.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python download_data.py   # downloads public Census files; verifies every input by checksum
python run_all.py         # or: make all
```

`download_data.py` places files under `data/` (set `WFM_DATA_DIR` to use another location) and
lists the inputs it cannot fetch automatically, with instructions. `run_all.py` rebuilds every
number, table, and figure and finishes by running `check_results.py`, which fails if a headline
number changes.

**Runtime** (measured on a laptop, clean environment): about 70 s from the inputs on the first run
(or `python run_all.py --reload`), about 15 s once `cache/` exists. Peak memory is about 2.6 GB.

## What produces what

| In the letter | Output file | Code |
|---|---|---|
| Study population: 18,107 tracts, 76.3 million residents | `outputs/summary.csv` (`tracts`, `residents`) | `load.build_tract_dataset` |
| Monitoring sites: 278 regulatory, 101 AQI-only, 379 total | `outputs/summary.csv` | `load.load_monitor_sites` |
| Share of smoke person-days, residents, and high-pollution person-days beyond 10/25/50 km (e.g., 30% / 26% / 19% at 25 km), both networks | `outputs/distance_table.csv` | `analysis.distance_table` |
| Non-smoke high-pollution person-days beyond 25 km (5% for definition b, 8% for a) and smoke ÷ non-smoke ratios | `outputs/distance_table.csv` | `analysis.distance_table`, `analysis.nonsmoke_highpm_days` |
| Residents averaging ≥10 smoke days/year beyond 25 km (9.1 million, 41%) | `outputs/summary.csv` (`residents_ge10_*`) | `analysis.summary` |
| Smoke curve above the residents curve beyond 10 km (regulatory network) | `outputs/summary.csv` (`curve_check_*`) | `analysis.curve_check` |
| Share of high-pollution tract-days that are smoke days (50%) | `outputs/summary.csv` | `analysis.nonsmoke_highpm_days` |
| Table 1: tracts, residents, smoke days, smoke person-days, sites, RR by state and urban/rural; state shares of smoke person-days beyond 25 km | `outputs/table1.csv` | `analysis.table1`, `analysis.state_share_beyond` |
| Monitoring-priority ranking (top 10 flagged) | `outputs/priority_tracts.csv` | `analysis.priority_ranking` |
| Figure 1 (A–E) | `figures/figure1.pdf` (vector), `figures/figure1.tiff` (600 dpi, 7 in wide) | `figure1.py` |

`stats.ipynb` shows the same tables interactively.

## Repository layout

| File | Purpose |
|---|---|
| `config.py` | Input and output locations (`WFM_DATA_DIR`, `WFM_CACHE_DIR`) |
| `load.py` | Reads inputs; builds the tract dataset; loads monitoring sites |
| `analysis.py` | Distances, non-smoke split, shares, Table 1, priority ranking, summary |
| `figure1.py` | Figure 1 |
| `run_all.py`, `Makefile` | Single entry point |
| `check_results.py` | Asserts headline numbers |
| `download_data.py` | Downloads public inputs; verifies all inputs by SHA-256 |
| `preprocessing/` | How the two daily tract-level PM2.5 inputs were made (provenance; not run by `run_all.py`) |

## Definitions

- **Smoke day:** tract wildfire PM2.5 ≥5 µg/m³.
- **High-pollution day:** tract all-source PM2.5 ≥35 µg/m³ (the 24-hour NAAQS level).
- **Non-smoke high-pollution day:** (a) all-source minus wildfire PM2.5 ≥35 µg/m³; (b) a high-pollution day that is not a smoke day (wildfire PM2.5 <5 µg/m³). Figure 1D uses (b).
- **Person-days:** days × 2020 tract population, summed over 2006–2020.
- **Distance:** great-circle distance from the Census 2020 population-weighted tract centroid to the nearest monitoring site.
- **Regulatory site:** a site with a parameter 88101 (FRM/FEM) monitor that has a NAAQS annual summary in the AQS file.
- **AQI-only site:** a site whose only PM2.5 monitor is a continuous (1-hour) parameter 88502 monitor. These feed the AQI but are not used for NAAQS compliance.
- **Site rule:** a site counts if any of its monitors reported at least one valid day in the AQS 2025 annual summary file (data through 2025-06-30). The same rule applies to both parameter codes. Colocated monitors are deduplicated by site (state–county–site number).
- **Priority score:** mean annual wildfire PM2.5 × tract share of the regional population × distance to the nearest regulatory or AQI-only site.
- **RR:** urban-to-rural population ratio ÷ urban-to-rural ratio of tracts containing a site. RR <1 means fewer monitored rural tracts than population implies.

## Data notes

- **Missing tracts:** 61 of the 18,168 2020 Census tracts in the 11 states (67,863 residents) are missing from the tract shapefile and are not analyzed.
- **Excluded tract:** El Paso County, TX tract 48141010222 is in the wildfire PM2.5 file but outside the study area and is excluded.
- **No smoke record:** 10,838 of 690,723 high-pollution tract-days (1.6%) have no wildfire PM2.5 record and are counted as non-smoke. This can only raise the non-smoke shares, so the smoke vs. non-smoke comparison is conservative.
- **All-source PM2.5 coverage:** the Swanson et al. product ends on 2020-12-14, so high-pollution days cover 2006-01-01 to 2020-12-14 (the last 17 days of 2020 are missing). 98 study tracts have no all-source PM2.5 data and contribute no high-pollution person-days.
- **Thresholds** are inclusive (≥). Values exactly at 5 or 35 µg/m³ are negligible (0 and 44 of about 98 million tract-days).

## Data sources

`python download_data.py` checks each file against the SHA-256 of the copy used for the letter.

| Input (under `data/`) | Source | Version / access date |
|---|---|---|
| `census/CenPop2020_Mean_TR.txt` | US Census Bureau, 2020 population-weighted tract centroids — downloaded automatically | accessed 2026-11-16 |
| `census/national_county2020.txt` | US Census Bureau, 2020 county names — downloaded automatically | accessed 2026-11-16 |
| `census/tl_2020_us_state.*` | US Census Bureau, TIGER/Line 2020 states — downloaded automatically | 2020 vintage |
| `census/nhgis_ds258_2020_tract_urban_rural.csv` | IPUMS NHGIS, 2020 Census DHC-A (ds258), table P2 "Urban and Rural", tract level (free account) | extract 2024-05-16 |
| `tracts/CensusTract2020_WesternUS.*` | Esri USA Census Tract Areas (2020 boundaries, with population), exported for the western states | exported 2023-06-14 |
| `aqs/annual_conc_by_monitor_2025.csv` | US EPA AQS annual summary by monitor, 2025 (<https://aqs.epa.gov/aqsweb/airdata/download_files.html>). EPA updates this file; the letter uses a snapshot with data through 2025-06-30. | downloaded 2025-09-26 |
| `pm25/smoke_pm25_tract_daily.parquet` | Childs et al. (2022), *ES&T* 56:13607, daily 10-km wildfire smoke PM2.5, Harvard Dataverse doi:10.7910/DVN/DJVMTV v1.0, area-weighted to tracts with `preprocessing/smoke_pm25_to_tract.ipynb` | v1.0, accessed 2024-10-29 |
| `pm25/allsource_pm25_tract_daily.parquet` | Swanson et al. (2022), *Sci Data* 9:466, doi:10.1038/s41597-022-01488-y, daily 1-km PM2.5 averaged to tracts, converted with `preprocessing/allsource_pm25_to_tract_parquet.py` | through 2020-12-14; built 2023 |

The snapshot and processed files that cannot be downloaded from their original sources (AQS
snapshot, tract shapefile export, and the two daily tract-level PM2.5 files) are to be deposited
with the paper: TODO(authors) deposit DOI. Upstream code by Childs et al. is at
<https://github.com/echolab-stanford/daily-10km-smokePM>.

## License

Code: MIT (see `LICENSE`). Input data remain under their providers' terms.
