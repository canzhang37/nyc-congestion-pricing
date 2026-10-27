# checks behind docs/replication.md
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pyfixest as pf

import replicate_bins as rb
import replicate_hourly as rh

OUT = Path("results/replication")
RAW = [f"data/raw/fhvhv_tripdata_{y}-{m:02d}.parquet" for y in (2024, 2025) for m in range(1, 6)]
X = "avg_miles + avg_time + avg_fare + avg_wait"


def table1(con):
    # the paper's Table 1 cells
    paper = pd.DataFrame({"date": ["2024-01-01", "2024-01-02", "2025-05-30", "2025-05-31"],
                          "paper_trips": [11, 7, 3, 1], "paper_miles": [17.08, 15.70, 16.68, 16.69],
                          "paper_time": [1644.45, 2006.29, 1714.67, 1775.00],
                          "paper_fare": [70.59, 92.59, 70.06, 88.97], "paper_wait": [93.64, 181.00, 31.67, 102.00]})
    files = [f"data/agg/cells_{m}.parquet" for m in ("2024-01", "2025-05")]
    ours = con.execute(f"""
        SELECT strftime(date, '%Y-%m-%d') AS date, sum(trips) AS trips,
               round(sum(miles) / sum(trips), 2) AS miles, round(sum(secs) / sum(trips), 2) AS time,
               round(sum(fare) / sum(trips), 2) AS fare, round(sum(wait_secs) / sum(trips), 2) AS wait
        FROM read_parquet({files}) WHERE pu_zone = 100 AND do_zone = 1 AND hour = 8
        GROUP BY 1""").df()
    t = paper.merge(ours, on="date", how="left")
    t["match"] = np.all([np.isclose(t[c], t["paper_" + c], atol=0.006)
                         for c in ("trips", "miles", "time", "fare", "wait")], axis=0)
    return t


def coef(df, rhs="treat", outcome="log1p", fe="od + date"):
    df["y"] = np.log1p(df.trips) if outcome == "log1p" else np.log(df.trips)
    m = pf.feols(f"y ~ {rhs} | {fe}", data=df, vcov={"CRV1": "od"}, fixef_rm="none", lean=True)
    return m.tidy()


def row(check, variant, series, tidy, paper, term="treat"):
    r = tidy.loc[term]
    return {"check": check, "variant": variant, "series": series, "estimate": r["Estimate"],
            "lo": r["2.5%"], "hi": r["97.5%"], "paper": paper}


def hourly_checks(con, rows):
    t = pd.read_csv("docs/targets_zhang2026_tableA2.csv").set_index("hour").loc[18]
    z38 = rh.crz_zones()
    lk = pd.read_csv("data/taxi_zone_lookup.csv")
    man = lk.Borough == "Manhattan"
    zone_sets = {"38 zones": z38, "36 zones": rh.crz_zones(strict=True),
                 "38 zones and the crossing zones": z38 + rh.CROSSING,
                 "Yellow Zone of the lookup": lk.loc[man & (lk.service_zone == "Yellow Zone"), "LocationID"].tolist(),
                 "all of Manhattan": lk.loc[man, "LocationID"].tolist()}
    df = rh.frame(con, 18, "uber", "janmay", z38)
    rows.append(row("covariates, log(trips)", "with covariates", "uber janmay", coef(df, "treat + " + X, "log"), t.uber_janmay))
    rows.append(row("covariates, log(trips)", "without covariates", "uber janmay", coef(df, "treat", "log"), t.uber_janmay))
    for name, z in zone_sets.items():
        df = rh.frame(con, 18, "uber", "janmay", z)
        rows.append(row("treated zones", name, "uber janmay", coef(df, "treat + " + X), t.uber_janmay))
    # other readings of the Feb-May fit
    rh.PERIODS["pre24_febmay25"] = [("2024-01-01", "2024-05-31"), ("2025-02-01", "2025-05-31")]
    for m, e24, e25 in [(2, 29, 28), (3, 31, 31), (4, 30, 30), (5, 31, 31)]:
        rh.PERIODS[f"m{m}"] = [(f"2024-{m:02d}-01", f"2024-{m:02d}-{e24}"), (f"2025-{m:02d}-01", f"2025-{m:02d}-{e25}")]
    for co in ("uber", "lyft"):
        paper = t[f"{co}_febmay"]
        for per, name in [("febmay", "Feb-May 2024 and 2025"), ("pre24_febmay25", "Jan-May 2024 and Feb-May 2025"),
                          ("m2", "February only"), ("m3", "March only"), ("m4", "April only"), ("m5", "May only")]:
            df = rh.frame(con, 18, co, per, z38)
            rows.append(row("February to May sample", name, f"{co} febmay", coef(df, "treat + " + X), paper))
        df = rh.frame(con, 18, co, "janmay", z38)
        jan = pd.to_datetime(df.date) < "2025-02-01"
        df["treat_febmay"] = df.treat * ~jan
        df["treat_jan"] = df.treat * jan
        rows.append(row("February to May sample", "Jan-May with separate Jan and Feb-May indicators", f"{co} febmay",
                        coef(df, "treat_jan + treat_febmay + " + X), paper, "treat_febmay"))
    print("hourly checks done", flush=True)


def raw_fare_bins(con, fare, b, where="TRUE"):
    inz = ", ".join(map(str, rh.crz_zones()))
    return con.execute(f"""
        SELECT * FROM (
        WITH r AS (SELECT *, {fare} AS f FROM read_parquet({RAW}, union_by_name = true)
                   WHERE hvfhs_license_num IN ('HV0003', 'HV0005'))
        SELECT PULocationID * 1000 + DOLocationID AS od, CAST(pickup_datetime AS DATE) AS date,
               CASE WHEN f < 10 THEN 0 WHEN f < 15 THEN 1 WHEN f < 20 THEN 2 WHEN f < 25 THEN 3
                    WHEN f < 30 THEN 4 WHEN f < 35 THEN 5 ELSE 6 END AS fare_bin,
               count(*) AS trips,
               max(((PULocationID IN ({inz}) OR DOLocationID IN ({inz})) AND pickup_datetime >= '{rh.START}')::INTEGER) AS treat,
               avg(trip_miles) AS avg_miles, avg(trip_time) AS avg_time, avg(f) AS avg_fare,
               avg(epoch(pickup_datetime) - epoch(request_datetime)) AS avg_wait
        FROM r WHERE {where} GROUP BY 1, 2, 3) WHERE fare_bin = {b}""").df()


def bin_checks(con, rows):
    t = pd.read_csv("docs/targets_zhang2026_tableA1.csv").set_index(["dim", "bin"])
    z38 = rh.crz_zones()
    for dim in ("dist", "fare"):
        paper = t.loc[(dim, 0), "estimate"]
        files = [f"data/agg/cells_{y}-{m:02d}.parquet" for y in (2024, 2025) for m in range(1, 6)]
        hourly = []
        for h in range(24):
            df = rb.frame(con, dim, 0, z38, hour=h)
            hourly.append(coef(df, "treat + " + X).loc["treat", "Estimate"])
        rows.append({"check": "pooling over hours", "variant": "mean of 24 hourly fits", "series": f"{dim} bin 0",
                     "estimate": np.mean(hourly), "lo": np.nan, "hi": np.nan, "paper": paper})
        df = rb.frame(con, dim, 0, z38)
        rows.append(row("pooling over hours", "OD-date panel", f"{dim} bin 0", coef(df, "treat + " + X), paper))
    print("pooling checks done", flush=True)
    paper0 = t.loc[("fare", 0), "estimate"]
    for name, where in [("zero and negative fares kept", "TRUE"), ("zero and negative fares dropped", "f > 0")]:
        df = raw_fare_bins(con, "base_passenger_fare", 0, where)
        rows.append(row("$0-10 bin", name, "fare bin 0", coef(df, "treat + " + X), paper0))
    for b in range(7):
        # one bin at a time
        df = raw_fare_bins(con, "base_passenger_fare - coalesce(cbd_congestion_fee, 0)", b)
        rows.append(row("fare bins on base fare less the charge", f"bin {b}", f"fare bin {b}",
                        coef(df, "treat + " + X), t.loc[("fare", b), "estimate"]))
    print("fare checks done", flush=True)


def main():
    con = duckdb.connect()
    con.execute("SET memory_limit = '3GB'; SET threads = 4; SET temp_directory = 'data/tmp'")
    t1 = table1(con)
    t1.to_csv(OUT / "table1_cells.csv", index=False)
    print(t1.to_string(index=False), flush=True)
    rows = []
    hourly_checks(con, rows)
    bin_checks(con, rows)
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "diagnostics.csv", index=False)
    print(d.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
