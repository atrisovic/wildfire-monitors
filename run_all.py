"""Regenerate every number, table, and figure in the EHP letter from the input data.

    python run_all.py            # use caches in cache/ when present
    python run_all.py --reload   # rebuild everything from data/

Steps: tract dataset (load.py) -> distances, non-smoke split, tables (analysis.py)
-> outputs/*.csv -> figures/figure1.pdf and .tiff (figure1.py) -> checks (check_results.py).
"""
import argparse
import runpy
import time

import check_results
from analysis import build, write_outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reload", action="store_true", help="ignore caches and rebuild from data/")
    args = parser.parse_args()

    t0 = time.time()
    print("1/4  Building tract dataset and site networks ...")
    tracts, sites = build(reload=args.reload)
    print(f"     {len(tracts):,} tracts, {int(sites.regulatory.sum())} regulatory + "
          f"{int((~sites.regulatory).sum())} AQI-only sites ({time.time() - t0:.0f} s)")

    print("2/4  Writing outputs/ ...")
    for name in write_outputs(tracts, sites):
        print(f"     outputs/{name}")

    print("3/4  Drawing Figure 1 ...")
    runpy.run_path("figure1.py", run_name="__main__")

    print("4/4  Checking headline numbers ...")
    check_results.main()
    print(f"Done in {time.time() - t0:.0f} s.")


if __name__ == "__main__":
    main()
