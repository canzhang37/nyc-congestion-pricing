# PySpark rebuild of the cells, vs data/agg
import argparse
import csv
import time
from pathlib import Path

from pyspark.sql import SparkSession, functions as F

RAW = Path("data/raw")
AGG = Path("data/agg")
OUT = Path("results/checks/spark_vs_duckdb.csv")
KEYS = ["pu_zone", "do_zone", "date", "hour", "company", "dist_bin", "fare_bin"]
INTS = ["trips", "charged", "secs", "wait_secs", "shared_req"]
FLOATS = ["fee", "miles", "fare", "driver_pay"]


def bins(col, cuts):
    e = None
    for i, c in enumerate(cuts):
        e = F.when(col < c, i) if e is None else e.when(col < c, i)
    # NULL goes to the last bin, as in DuckDB
    return e.otherwise(len(cuts))


def cells(spark, month):
    df = spark.read.parquet(str(RAW / f"fhvhv_tripdata_{month}.parquet"))
    df = df.where(F.col("hvfhs_license_num").isin("HV0003", "HV0005"))
    fee = F.col("cbd_congestion_fee") if "cbd_congestion_fee" in df.columns else F.lit(0.0)
    secs = lambda c: F.col(c).cast("timestamp").cast("long")
    return (df.select(
        F.col("PULocationID").cast("int").alias("pu_zone"),
        F.col("DOLocationID").cast("int").alias("do_zone"),
        F.to_date("pickup_datetime").alias("date"),
        F.hour("pickup_datetime").alias("hour"),
        F.when(F.col("hvfhs_license_num") == "HV0003", "uber").otherwise("lyft").alias("company"),
        bins(F.col("trip_miles"), [1, 2, 5, 10, 20]).alias("dist_bin"),
        bins(F.col("base_passenger_fare"), [10, 15, 20, 25, 30, 35]).alias("fare_bin"),
        fee.alias("f"), "trip_miles", "trip_time", "base_passenger_fare", "driver_pay",
        (secs("pickup_datetime") - secs("request_datetime")).alias("wait"),
        (F.col("shared_request_flag") == "Y").cast("int").alias("shared"))
        .groupBy(KEYS)
        .agg(F.count("*").alias("trips"),
             F.sum(F.when(F.col("f") > 0, 1).otherwise(0)).alias("charged"),
             F.sum("f").cast("float").alias("fee"),
             F.sum("trip_miles").cast("float").alias("miles"),
             F.sum("trip_time").alias("secs"),
             F.sum("base_passenger_fare").cast("float").alias("fare"),
             F.sum("wait").alias("wait_secs"),
             F.sum("driver_pay").cast("float").alias("driver_pay"),
             F.sum(F.coalesce("shared", F.lit(0))).alias("shared_req")))


def compare(spark, month):
    s = cells(spark, month)
    d = spark.read.parquet(str(AGG / f"cells_{month}.parquet"))
    d = d.select([F.col(k).cast("int").alias(k) if k not in ("date", "company") else F.col(k) for k in KEYS]
                 + INTS + FLOATS)
    j = s.alias("s").join(d.alias("d"), KEYS, "full_outer")
    in_s, in_d = F.col("s.trips").isNotNull(), F.col("d.trips").isNotNull()
    both = in_s & in_d
    aggs = [F.sum(in_s.cast("int")).alias("cells_spark"), F.sum(in_d.cast("int")).alias("cells_duckdb"),
            F.sum((in_s & ~in_d).cast("int")).alias("only_spark"), F.sum((in_d & ~in_s).cast("int")).alias("only_duckdb"),
            F.sum("s.trips").alias("trips_spark"), F.sum("d.trips").alias("trips_duckdb")]
    for c in INTS:
        aggs.append(F.sum((both & ~F.col(f"s.{c}").eqNullSafe(F.col(f"d.{c}"))).cast("int")).alias(f"diff_{c}"))
    for c in FLOATS:
        rel = F.abs(F.col(f"s.{c}") - F.col(f"d.{c}")) / F.greatest(F.abs(F.col(f"d.{c}")), F.lit(1.0))
        aggs.append(F.sum((both & (rel > 1e-6)).cast("int")).alias(f"diff_{c}"))
        aggs.append(F.max(F.when(both, rel)).alias(f"maxrel_{c}"))
    return j.agg(*aggs).collect()[0].asDict()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ranges", nargs="+", help="pairs of first and last month")
    a = p.parse_args()
    months = []
    for first, last in zip(a.ranges[::2], a.ranges[1::2]):
        y, m = map(int, first.split("-"))
        y1, m1 = map(int, last.split("-"))
        while (y, m) <= (y1, m1):
            months.append(f"{y}-{m:02d}")
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    spark = (SparkSession.builder.master("local[4]").appName("tlc-cells")
             .config("spark.driver.memory", "6g")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.sql.shuffle.partitions", "64")
             .config("spark.ui.enabled", "false").getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    rows = []
    for month in months:
        t0 = time.time()
        r = {"month": month, **compare(spark, month)}
        r["seconds"] = round(time.time() - t0)
        rows.append(r)
        print(month, r["trips_spark"], r["only_spark"], r["only_duckdb"],
              sum(r[f"diff_{c}"] for c in INTS + FLOATS), f"{r['seconds']}s", flush=True)
    spark.stop()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
