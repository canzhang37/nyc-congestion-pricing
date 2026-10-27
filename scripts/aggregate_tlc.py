# monthly files -> cell sums, one file a month
# sums, so cells collapse by adding
import argparse
import time
from pathlib import Path

import duckdb

RAW = Path("data/raw")
AGG = Path("data/agg")

# the paper's bins: miles and base fare
SQL = """
COPY (
  SELECT
    CAST(PULocationID AS SMALLINT) AS pu_zone, CAST(DOLocationID AS SMALLINT) AS do_zone,
    CAST(pickup_datetime AS DATE) AS date,
    CAST(hour(pickup_datetime) AS TINYINT) AS hour,
    CASE hvfhs_license_num WHEN 'HV0003' THEN 'uber' ELSE 'lyft' END AS company,
    CASE WHEN trip_miles < 1 THEN 0 WHEN trip_miles < 2 THEN 1 WHEN trip_miles < 5 THEN 2
         WHEN trip_miles < 10 THEN 3 WHEN trip_miles < 20 THEN 4 ELSE 5 END::TINYINT AS dist_bin,
    CASE WHEN base_passenger_fare < 10 THEN 0 WHEN base_passenger_fare < 15 THEN 1
         WHEN base_passenger_fare < 20 THEN 2 WHEN base_passenger_fare < 25 THEN 3
         WHEN base_passenger_fare < 30 THEN 4 WHEN base_passenger_fare < 35 THEN 5
         ELSE 6 END::TINYINT AS fare_bin,
    CAST(count(*) AS INTEGER) AS trips,
    CAST(count(*) FILTER (WHERE {fee} > 0) AS INTEGER) AS charged,
    CAST(sum({fee}) AS FLOAT) AS fee,
    CAST(sum(trip_miles) AS FLOAT) AS miles,
    CAST(sum(trip_time) AS BIGINT) AS secs,
    CAST(sum(base_passenger_fare) AS FLOAT) AS fare,
    CAST(sum(epoch(pickup_datetime) - epoch(request_datetime)) AS BIGINT) AS wait_secs,
    CAST(sum(driver_pay) AS FLOAT) AS driver_pay,
    CAST(count(*) FILTER (WHERE shared_request_flag = 'Y') AS INTEGER) AS shared_req
  FROM read_parquet('{src}')
  WHERE hvfhs_license_num IN ('HV0003', 'HV0005')
  GROUP BY ALL
  -- sorted keys compress better than hash order
  ORDER BY pu_zone, do_zone, company, hour, date, dist_bin, fare_bin
) TO '{dest}' (FORMAT parquet, COMPRESSION zstd)
"""


def months(first, last):
    y, m = map(int, first.split("-"))
    y1, m1 = map(int, last.split("-"))
    while (y, m) <= (y1, m1):
        yield f"{y}-{m:02d}"
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def aggregate(con, month, force=False):
    src = RAW / f"fhvhv_tripdata_{month}.parquet"
    dest = AGG / f"cells_{month}.parquet"
    if dest.exists() and not force:
        return "skip"
    if not src.exists():
        return "no raw file yet"
    cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{src}')").fetchall()}
    # no charge column before 2025
    fee = "cbd_congestion_fee" if "cbd_congestion_fee" in cols else "0.0"
    tmp = dest.with_suffix(".tmp")
    con.execute(SQL.format(fee=fee, src=src.as_posix(), dest=tmp.as_posix()))
    tmp.replace(dest)
    return "done" if fee != "0.0" else "done (no fee column)"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("first")
    p.add_argument("last")
    p.add_argument("--force", action="store_true")
    a = p.parse_args()
    AGG.mkdir(parents=True, exist_ok=True)
    Path("data/tmp").mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    # 16 GB laptop: small memory, spill to disk
    con.execute("SET memory_limit = '3GB'; SET threads = 4; SET temp_directory = 'data/tmp'")
    con.execute("SET preserve_insertion_order = false")
    for month in months(a.first, a.last):
        t0 = time.time()
        status = aggregate(con, month, a.force)
        print(month, status, f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
