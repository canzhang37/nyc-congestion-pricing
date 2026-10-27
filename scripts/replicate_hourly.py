# Part A: the paper's hourly model
import argparse
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import psutil
import pyfixest as pf

START = "2025-01-05"
PERIODS = {"janmay": [("2024-01-01", "2024-05-31"), ("2025-01-01", "2025-05-31")],
           "jan": [("2024-01-01", "2024-01-31"), ("2025-01-01", "2025-01-31")],
           "febmay": [("2024-02-01", "2024-05-31"), ("2025-02-01", "2025-05-31")]}
# below 95% but south of 60th Street
TIP_ZONES = [12, 88]
# zones across 60th Street
CROSSING = [43, 140, 141, 142, 143, 237]
FML = "y ~ treat + avg_miles + avg_time + avg_fare + avg_wait | od + date"


def crz_zones(strict=False):
    z = pd.read_csv("results/checks/manhattan_zones.csv")
    zones = z.loc[z.charged_share >= 0.95, "zone"].tolist()
    return sorted(zones if strict else zones + TIP_ZONES)


def frame(con, hour, company, period, zones, drop=()):
    months = sorted({d[:7] for a, b in PERIODS[period] for d in pd.date_range(a, b).strftime("%Y-%m-%d")})
    files = [f"data/agg/cells_{m}.parquet" for m in months]
    win = " OR ".join(f"date BETWEEN '{a}' AND '{b}'" for a, b in PERIODS[period])
    cond = "" if company == "all" else f"AND company = '{company}'"
    inz = ", ".join(map(str, zones))
    if drop:
        out = ", ".join(map(str, drop))
        cond += f" AND pu_zone NOT IN ({out}) AND do_zone NOT IN ({out})"
    return con.execute(f"""
        SELECT pu_zone::INTEGER * 1000 + do_zone AS od, date, sum(trips) AS trips,
               ((pu_zone IN ({inz}) OR do_zone IN ({inz})) AND date >= '{START}')::INTEGER AS treat,
               sum(miles) / sum(trips) AS avg_miles, sum(secs) / sum(trips) AS avg_time,
               sum(fare) / sum(trips) AS avg_fare, sum(wait_secs) / sum(trips) AS avg_wait
        FROM read_parquet({files})
        WHERE hour = {hour} AND ({win}) {cond}
        GROUP BY pu_zone, do_zone, date""").df()


def fit(df, outcome="log"):
    # log(1 + trips) matches the paper
    df["y"] = np.log(df.trips) if outcome == "log" else np.log1p(df.trips)
    # keep singletons, as PanelOLS does
    m = pf.feols(FML, data=df, vcov={"CRV1": "od"}, fixef_rm="none", lean=True, copy_data=False)
    t = m.tidy().loc["treat"]
    return {"estimate": t["Estimate"], "se": t["Std. Error"], "lo": t["2.5%"], "hi": t["97.5%"],
            "n": m._N, "od_pairs": df.od.nunique()}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--hours", default="0-23", help="e.g. 18 or 0-23")
    p.add_argument("--company", default="all", choices=["all", "uber", "lyft"])
    p.add_argument("--period", default="janmay", choices=list(PERIODS))
    p.add_argument("--outcome", default="log", choices=["log", "log1p"])
    p.add_argument("--zones36", action="store_true")
    p.add_argument("--drop-crossing", action="store_true", help="drop OD pairs touching the zones across 60th Street")
    p.add_argument("--out", help="CSV to append rows to")
    a = p.parse_args()
    lo, _, hi = a.hours.partition("-")
    hours = range(int(lo), int(hi or lo) + 1)
    con = duckdb.connect()
    con.execute("SET memory_limit = '3GB'; SET threads = 4; SET temp_directory = 'data/tmp'")
    zones = crz_zones(a.zones36)
    drop = CROSSING if a.drop_crossing else ()
    label = ("36" if a.zones36 else "38") + (" no crossing" if a.drop_crossing else "")
    for h in hours:
        t0 = time.time()
        res = fit(frame(con, h, a.company, a.period, zones, drop), a.outcome)
        row = {"company": a.company, "period": a.period, "outcome": a.outcome,
               "zones": label, "hour": h, **res}
        peak = psutil.Process().memory_info().peak_wset / 1e9
        print(f"{h:2d} {res['estimate']:.4f} ({res['lo']:.4f}, {res['hi']:.4f}) n {res['n']:,} "
              f"{time.time() - t0:.0f}s peak {peak:.1f} GB", flush=True)
        if a.out:
            out = Path(a.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame([row]).to_csv(out, mode="a", header=not out.exists(), index=False)


if __name__ == "__main__":
    main()
