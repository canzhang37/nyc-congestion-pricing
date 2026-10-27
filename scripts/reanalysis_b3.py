# Part B3: fare groups fixed before the policy
from pathlib import Path

import duckdb
import pandas as pd

from replicate_hourly import START, crz_zones, fit

RAW24 = [f"data/raw/fhvhv_tripdata_2024-{m:02d}.parquet" for m in range(1, 6)]
CELLS = [f"data/agg/cells_{y}-{m:02d}.parquet" for y in (2024, 2025) for m in range(1, 6)]
GROUPS = Path("data/b3_groups.parquet")
OUT = Path("results/reanalysis")
# paper's fare bins on the 2024 median
GROUP = """CASE WHEN median_fare < 10 THEN 0 WHEN median_fare < 15 THEN 1 WHEN median_fare < 20 THEN 2
                WHEN median_fare < 25 THEN 3 WHEN median_fare < 30 THEN 4 WHEN median_fare < 35 THEN 5 ELSE 6 END"""


def build_groups(con):
    # medians need the trip rows
    con.execute(f"""COPY (
        SELECT PULocationID::SMALLINT AS pu_zone, DOLocationID::SMALLINT AS do_zone,
               hour(pickup_datetime)::TINYINT AS hour, median(base_passenger_fare) AS median_fare
        FROM read_parquet({RAW24}) WHERE hvfhs_license_num IN ('HV0003', 'HV0005')
        GROUP BY ALL) TO '{GROUPS.as_posix()}' (FORMAT parquet)""")


def frame(con, g, zones):
    inz = ", ".join(map(str, zones))
    return con.execute(f"""
        WITH grp AS (SELECT pu_zone, do_zone, hour, {GROUP} AS g FROM '{GROUPS.as_posix()}')
        SELECT c.pu_zone::INTEGER * 1000 + c.do_zone AS od, c.date, sum(c.trips) AS trips,
               ((c.pu_zone IN ({inz}) OR c.do_zone IN ({inz})) AND c.date >= '{START}')::INTEGER AS treat,
               sum(c.miles) / sum(c.trips) AS avg_miles, sum(c.secs) / sum(c.trips) AS avg_time,
               sum(c.fare) / sum(c.trips) AS avg_fare, sum(c.wait_secs) / sum(c.trips) AS avg_wait
        FROM read_parquet({CELLS}) c JOIN grp USING (pu_zone, do_zone, hour)
        WHERE grp.g = {g}
        GROUP BY c.pu_zone, c.do_zone, c.date""").df()


def main():
    con = duckdb.connect()
    con.execute("SET memory_limit = '2GB'; SET threads = 2; SET temp_directory = 'data/tmp'")
    if not GROUPS.exists():
        build_groups(con)
    # trips in grouped pair-hours, by year
    cover = con.execute(f"""
        WITH grp AS (SELECT pu_zone, do_zone, hour FROM '{GROUPS.as_posix()}')
        SELECT year(c.date) AS year, sum(c.trips) AS trips,
               sum(c.trips) FILTER (WHERE grp.hour IS NOT NULL) AS trips_with_group
        FROM read_parquet({CELLS}) c LEFT JOIN grp USING (pu_zone, do_zone, hour)
        GROUP BY 1 ORDER BY 1""").df()
    cover["share"] = cover.trips_with_group / cover.trips
    print(cover.to_string(index=False))

    t = pd.read_csv("docs/targets_zhang2026_tableA1.csv").query("dim == 'fare'").set_index("bin")
    own = pd.read_csv(OUT / "../replication/bins.csv").query("dim == 'fare' and outcome == 'log1p'").set_index("bin")
    zones = crz_zones()
    rows = []
    for g in range(7):
        df = frame(con, g, zones)
        r = fit(df, "log1p")
        rows.append({"group": g, "label": t.loc[g, "label"], **r,
                     "trips_2024": df.loc[pd.to_datetime(df.date).dt.year == 2024, "trips"].sum(),
                     "own_fare_estimate": own.loc[g, "estimate"], "paper": t.loc[g, "estimate"]})
        print(f"{t.loc[g, 'label']:7s} {r['estimate']:.4f} ({r['lo']:.4f}, {r['hi']:.4f})  own fare {own.loc[g, 'estimate']:.4f}  "
              f"paper {t.loc[g, 'estimate']:.3f}  rows {len(df):,}", flush=True)
    res = pd.DataFrame(rows)
    # amendment 8 test, lowest group
    low = res.iloc[0]
    paper = t.loc[0, "estimate"]
    verdict = "confirmed" if low.lo > paper else "rejected" if low.hi < paper else "undecided"
    res["prediction"] = [verdict] + [""] * 6
    print(f"prediction for the lowest group: {verdict}")
    OUT.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT / "b3.csv", index=False)
    cover.to_csv(OUT / "b3_coverage.csv", index=False)


if __name__ == "__main__":
    main()
