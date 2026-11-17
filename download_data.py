"""Download the public inputs and verify every input against the version used in the letter.

    python download_data.py            # download what can be downloaded, then verify all
    python download_data.py --verify   # verify only

Files go under WFM_DATA_DIR (default ./data) in the layout config.py expects. Inputs that
cannot be fetched automatically are listed with exact instructions. Checksums are SHA-256
of the copies used for the letter, so a different version is reported, not used silently.
"""
import argparse
import hashlib
import io
import os
import sys
import urllib.request
import zipfile

import config

# Deposit holding the processed inputs below that are not otherwise public.
# TODO(authors): set once the deposit exists. doi:10.7910/DVN/9VDUAP is the co-exposure
# project's deposit and does not contain these files.
PROCESSED_DEPOSIT = None

INPUTS = [
    {
        "path": config.CENPOP_PATH,
        "sha256": "137d5b7bc8139a385c2022f54a9aca00ea56bc5ad81c936cf8134e977d50d2c5",
        "what": "Census 2020 population-weighted tract centroids (CenPop2020_Mean_TR)",
        "url": "https://www2.census.gov/geo/docs/reference/cenpop2020/tract/CenPop2020_Mean_TR.txt",
        "accessed": "2026-11-16",
    },
    {
        "path": config.COUNTY_NAMES_PATH,
        "sha256": "9f6e5f6eb6ac2f5e9a36d5fd01dec77991bddc75118f748a069441a4782970d6",
        "what": "Census 2020 county names (national_county2020)",
        "url": "https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt",
        "accessed": "2026-11-16",
    },
    {
        "path": config.STATES_SHP_PATH,
        "sha256": "3f1f6d1ed1665a3c798dca357e2b795e114ce99d508cb1a8d914f4ee608f199a",
        "what": "Census TIGER/Line 2020 state boundaries (tl_2020_us_state)",
        "zip_url": "https://www2.census.gov/geo/tiger/TIGER2020/STATE/tl_2020_us_state.zip",
        "accessed": "2023-10-24",
    },
    {
        "path": config.MONITORS_PATH,
        "sha256": "c44dc6274b89d339615136c455c1a3c02fb335fdd634ee66ee8822a4897ee0c2",
        "what": "US EPA AQS annual summary by monitor, 2025 (snapshot: data through 2025-06-30)",
        "manual": ("EPA updates this file, so a current download will differ from the snapshot used "
                   "(downloaded 2025-09-26). Get the snapshot from the authors' deposit. The live file "
                   "is https://aqs.epa.gov/aqsweb/airdata/annual_conc_by_monitor_2025.zip"),
        "deposit": True,
    },
    {
        "path": config.URBAN_RURAL_PATH,
        "sha256": "74805d538ec742988f1e6ff453be65ead0be56bce487ffee36cb57f76de09e68",
        "what": "2020 Census urban/rural population by tract (NHGIS ds258, table P2 / U7I)",
        "manual": ("IPUMS NHGIS (https://www.nhgis.org, free account): dataset 2020_DHCa "
                   "(2020 Census: DHC - P & H Tables), table P2 'Urban and Rural' (NHGIS code U7I), "
                   "geographic level Census Tract, CSV. Save the CSV under this name. "
                   "Extract used: nhgis0006_ds258_2020_tract, 2024-05-16."),
    },
    {
        "path": config.TRACTS_SHP_PATH,
        "sha256": "1e919f45c2d9952fc7b5abac2f2922916f273fe7e09c9cd80a90da291598d876",
        "what": "2020 census tract boundaries with population, western US (with .dbf/.shx/.prj)",
        "manual": ("Esri USA Census Tract Areas (2020 Census boundaries, ArcGIS Living Atlas), "
                   "exported 2023-06-14 for the western states (fields STATE_ABBR, FIPS, POPULATION, "
                   "SQMI). Get the exported shapefile from the authors' deposit."),
        "deposit": True,
    },
    {
        "path": config.SMOKE_PM25_PATH,
        "sha256": "69a1a9fa17179f75a9d739753419c0f9daa6b0ff2fdd387f924bff82b87e74c8",
        "what": "Daily wildfire smoke PM2.5 by tract, 2006-2020 (from Childs et al.)",
        "manual": ("Get from the authors' deposit, or rebuild with "
                   "preprocessing/smoke_pm25_to_tract.ipynb from Childs et al. v1.0, Harvard Dataverse "
                   "doi:10.7910/DVN/DJVMTV, file smokePM2pt5_predictions_daily_10km_20060101-20201231.csv "
                   "(1,778,985,211 bytes) and 10km_grid_wgs84.shp; accessed 2024-10-29."),
        "deposit": True,
    },
    {
        "path": config.ALLSOURCE_PM25_PATH,
        "sha256": "87a860698828d36896108e6dc1204fea3d4e1d79845e8826d01d97badcfb9ac7",
        "what": "Daily all-source PM2.5 by tract, 2006-2020-12-14 (from Swanson et al.)",
        "manual": ("Get from the authors' deposit, or rebuild with "
                   "preprocessing/allsource_pm25_to_tract_parquet.py from the tract-level space-time "
                   "cube of Swanson et al. (2022) daily 1-km PM2.5 (doi:10.1038/s41597-022-01488-y; "
                   "see the paper's Data Records for the grid files). Cube built 2023."),
        "deposit": True,
    },
]


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def download(item):
    os.makedirs(os.path.dirname(item["path"]), exist_ok=True)
    req = urllib.request.Request(item.get("url") or item["zip_url"],
                                 headers={"User-Agent": "wildfire-monitors-data/1.0"})
    with urllib.request.urlopen(req) as r:
        payload = r.read()
    if "zip_url" in item:
        stem = os.path.splitext(os.path.basename(item["path"]))[0]
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            for name in z.namelist():
                if name.startswith(stem):
                    z.extract(name, os.path.dirname(item["path"]))
    else:
        with open(item["path"], "wb") as f:
            f.write(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verify", action="store_true", help="only check files already present")
    args = parser.parse_args()

    missing, mismatched = [], []
    for item in INPUTS:
        path = item["path"]
        if not os.path.exists(path) and not args.verify and ("url" in item or "zip_url" in item):
            print(f"downloading  {item['what']}")
            download(item)
        if not os.path.exists(path):
            missing.append(item)
            print(f"MISSING      {path}")
            continue
        ok = sha256(path) == item["sha256"]
        print(f"{'ok' if ok else 'DIFFERENT':12s} {path}")
        if not ok:
            mismatched.append(item)

    for item in missing:
        print(f"\n{item['path']}\n  {item['what']}\n  {item['manual']}")
        if item.get("deposit"):
            print(f"  Authors' deposit: {PROCESSED_DEPOSIT or 'TODO (not yet published)'}")
    for item in mismatched:
        print(f"\n{item['path']} differs from the version used in the letter "
              f"(expected sha256 {item['sha256'][:12]}...). Results may differ.")
    if missing or mismatched:
        sys.exit(1)
    print("\nAll inputs present and match the versions used in the letter.")


if __name__ == "__main__":
    main()
