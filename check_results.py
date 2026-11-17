"""Assert the headline numbers so a code or data change can't silently alter them.

Run after run_all.py (it is the last step of run_all.py). Exits non-zero on failure.
"""
import os
import sys

import pandas as pd

import config

EXPECTED_BEYOND_25KM_REGULATORY = {          # % beyond 25 km of the nearest regulatory site
    "Smoke person-days": 30.1,
    "Residents": 26.5,
    "Non-smoke high-pollution person-days (b)": 5.1,
    "Non-smoke high-pollution person-days (a)": 8.1,
}
EXPECTED_SUMMARY = {"tracts": 18107, "regulatory_sites": 278, "all_sites": 379}


def main():
    failures = []
    dist = pd.read_csv(os.path.join(config.OUTPUT_DIR, "distance_table.csv"))
    reg = dist[dist.network.str.startswith("Regulatory (88101)")].set_index("measure")
    for measure, expected in EXPECTED_BEYOND_25KM_REGULATORY.items():
        got = round(float(reg.loc[measure, "beyond_25km"]), 1)
        status = "ok" if got == expected else "FAIL"
        print(f"{status:4s}  {measure} beyond 25 km: {got} (expected {expected})")
        if got != expected:
            failures.append(measure)

    summ = pd.read_csv(os.path.join(config.OUTPUT_DIR, "summary.csv")).set_index("item")["value"]
    for item, expected in EXPECTED_SUMMARY.items():
        got = int(summ[item])
        status = "ok" if got == expected else "FAIL"
        print(f"{status:4s}  {item}: {got} (expected {expected})")
        if got != expected:
            failures.append(item)

    for name in ["figure1.pdf", "figure1.tiff"]:
        path = os.path.join(config.FIGURE_DIR, name)
        ok = os.path.exists(path)
        print(f"{'ok' if ok else 'FAIL':4s}  {path} exists")
        if not ok:
            failures.append(name)

    if failures:
        sys.exit(f"\n{len(failures)} check(s) failed: {', '.join(failures)}")
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
