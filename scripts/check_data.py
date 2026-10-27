# data checks before any outcome
import argparse
from pathlib import Path

import duckdb

RAW = Path("data/raw")
AGG = Path("data/agg")
OUT = Path("results/checks")
START = "2025-01-05"


def months(first, last):
    y, m = map(int, first.split("-"))
    y1, m1 = map(int, last.split("-"))
    while (y, m) <= (y1, m1):
        yield f"{y}-{m:02d}"
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("first")
    p.add_argument("last")
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET memory_limit = '3GB'; SET threads = 4; SET temp_directory = 'data/tmp'")

    # 1. months, date ranges, rows
    rows = []
    for m in months(a.first, a.last):
        raw, agg = RAW / f"fhvhv_tripdata_{m}.parquet", AGG / f"cells_{m}.parquet"
        if not agg.exists():
            rows.append((m, raw.exists(), False, None, None, None, None, None))
            continue
        r = con.execute(f"""SELECT min(date), max(date), count(DISTINCT date),
            sum(trips) FILTER (WHERE company = 'uber'), sum(trips) FILTER (WHERE company = 'lyft')
            FROM '{agg.as_posix()}'""").fetchone()
        rows.append((m, raw.exists(), True, *r))
    con.execute("""CREATE TABLE months (month VARCHAR, raw_file BOOLEAN, aggregated BOOLEAN,
        first_date DATE, last_date DATE, days INTEGER, uber_trips BIGINT, lyft_trips BIGINT)""")
    con.executemany("INSERT INTO months VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    con.execute(f"COPY months TO '{OUT}/months.csv' (HEADER)")
    print(con.sql("SELECT * FROM months").df().to_string(index=False))

    files = [(AGG / f"cells_{m}.parquet").as_posix() for m in months(a.first, a.last)
             if (AGG / f"cells_{m}.parquet").exists()]
    con.execute(f"CREATE VIEW cells AS SELECT * FROM read_parquet({files})")
    con.execute("""CREATE TABLE zones AS SELECT LocationID AS zone, Borough AS borough, Zone AS name
        FROM read_csv('data/taxi_zone_lookup.csv')""")

    # 2. no charge before the start date
    pre = con.execute(f"SELECT sum(charged), sum(fee) FROM cells WHERE date < '{START}'").fetchone()
    print(f"\ncharged trips before {START}: {pre[0]} (fee total {pre[1]})")
    # Jan 4 late pickups charged after midnight
    print(con.sql(f"""SELECT date, hour, sum(charged) AS charged FROM cells
        WHERE date < '{START}' AND charged > 0 GROUP BY ALL ORDER BY ALL""").df().to_string(index=False))

    # 3. zone rule: >= 95% of intra-zone trips charged
    con.execute(f"""CREATE TABLE crz AS
        SELECT z.zone, z.name, sum(trips) AS intra_trips, sum(charged) / sum(trips) AS charged_share
        FROM cells c JOIN zones z ON c.pu_zone = z.zone
        WHERE c.pu_zone = c.do_zone AND z.borough = 'Manhattan'
          AND date BETWEEN '{START}' AND '2025-05-31'
        GROUP BY ALL ORDER BY charged_share DESC""")
    con.execute(f"COPY crz TO '{OUT}/manhattan_zones.csv' (HEADER)")
    print(con.sql("SELECT * FROM crz").df().to_string(index=False))
    con.execute("CREATE TABLE inzone AS SELECT zone FROM crz WHERE charged_share >= 0.95")

    # 4. charge by OD type and hour, through trips
    con.execute(f"""CREATE TABLE fee_od AS
        SELECT CASE WHEN pu_zone IN (SELECT zone FROM inzone) AND do_zone IN (SELECT zone FROM inzone) THEN 'intra'
                    WHEN do_zone IN (SELECT zone FROM inzone) THEN 'inbound'
                    WHEN pu_zone IN (SELECT zone FROM inzone) THEN 'outbound'
                    ELSE 'neither' END AS od_type,
               hour, sum(trips) AS trips, sum(charged) AS charged,
               sum(charged) / sum(trips) AS charged_share, sum(fee) / sum(charged) AS fee_per_charged
        FROM cells WHERE date >= '{START}' AND date <= '2025-05-31'
        GROUP BY ALL ORDER BY od_type, hour""")
    con.execute(f"COPY fee_od TO '{OUT}/fee_by_od_type_hour.csv' (HEADER)")
    print(con.sql("""SELECT od_type, sum(charged) / sum(trips) AS charged_share,
        min(charged_share) AS min_hour, max(charged_share) AS max_hour,
        sum(charged) AS charged FROM fee_od GROUP BY 1 ORDER BY 1""").df().to_string(index=False))
    tot = con.execute("SELECT sum(charged) FILTER (WHERE od_type = 'neither') / sum(charged) FROM fee_od").fetchone()[0]
    print(f"share of charged trips with neither end in the zone: {tot:.4f}")

    # 5. panel size vs the paper
    win = "(date BETWEEN '2024-01-01' AND '2024-05-31' OR date BETWEEN '2025-01-01' AND '2025-05-31')"
    n = con.execute(f"""SELECT
        (SELECT count(*) FROM (SELECT DISTINCT pu_zone, do_zone FROM cells WHERE {win})),
        (SELECT count(*) FROM (SELECT DISTINCT pu_zone, do_zone, date FROM cells WHERE {win})),
        (SELECT count(*) FROM (SELECT DISTINCT pu_zone, do_zone, date, hour FROM cells WHERE {win}))""").fetchone()
    print(f"\nOD pairs {n[0]:,}, OD x date {n[1]:,}, OD x date x hour {n[2]:,}")
    # the paper's count matches OD x date
    with open(OUT / "panel_size.csv", "w") as f:
        f.write("level,ours,paper\n")
        f.write(f"od_pairs,{n[0]},65116\nod_date,{n[1]},11020491\nod_date_hour,{n[2]},\n")


if __name__ == "__main__":
    main()
