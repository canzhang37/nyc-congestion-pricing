# Part A, Table A.1: one fit per bin
# daily panel, OD pair x date
import argparse
from pathlib import Path

import duckdb
import pandas as pd

from replicate_hourly import PERIODS, START, crz_zones, fit


def frame(con, dim, b, zones, period="janmay", hour=None):
    files = [f"data/agg/cells_{y}-{m:02d}.parquet" for y in (2024, 2025) for m in range(1, 6)]
    win = " OR ".join(f"date BETWEEN '{a}' AND '{c}'" for a, c in PERIODS[period])
    inz = ", ".join(map(str, zones))
    h = "" if hour is None else f"AND hour = {hour}"
    return con.execute(f"""
        SELECT pu_zone::INTEGER * 1000 + do_zone AS od, date, sum(trips) AS trips,
               ((pu_zone IN ({inz}) OR do_zone IN ({inz})) AND date >= '{START}')::INTEGER AS treat,
               sum(miles) / sum(trips) AS avg_miles, sum(secs) / sum(trips) AS avg_time,
               sum(fare) / sum(trips) AS avg_fare, sum(wait_secs) / sum(trips) AS avg_wait
        FROM read_parquet({files})
        WHERE {dim}_bin = {b} AND ({win}) {h}
        GROUP BY pu_zone, do_zone, date""").df()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--outcome", nargs="+", default=["log1p"], choices=["log", "log1p"])
    p.add_argument("--out", default="results/replication/bins.csv")
    a = p.parse_args()
    con = duckdb.connect()
    con.execute("SET memory_limit = '3GB'; SET threads = 4; SET temp_directory = 'data/tmp'")
    t = pd.read_csv("docs/targets_zhang2026_tableA1.csv")
    zones = crz_zones()
    rows = []
    for oc in a.outcome:
        for r in t.itertuples():
            res = fit(frame(con, r.dim, r.bin, zones), oc)
            # bin rule: inside interval or within 0.01
            inside = r.lo <= res["estimate"] <= r.hi
            close = abs(res["estimate"] - r.estimate) <= 0.01
            rows.append({"dim": r.dim, "bin": r.bin, "label": r.label, "outcome": oc, **res,
                         "paper": r.estimate, "paper_lo": r.lo, "paper_hi": r.hi,
                         "inside": inside, "replicates": inside or close})
            print(f"{oc:5s} {r.dim} {r.label:9s} {res['estimate']:.4f} ({res['lo']:.4f}, {res['hi']:.4f})  "
                  f"paper {r.estimate:.3f}  {'replicates' if inside or close else ''}", flush=True)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)


if __name__ == "__main__":
    main()
