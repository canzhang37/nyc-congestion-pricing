# New York's congestion charge and ride-hail trips: a replication and reanalysis

On January 5, 2025, New York began charging $1.50 for each Uber and Lyft trip that travels to, from, within or through Manhattan south of 60th Street. Zhang, Sang and Wu (2026, Transportation Research Part A) estimated the effect of this charge on ride-hail trips with origin-destination by hour panels built from the public trip records of the NYC Taxi and Limousine Commission (TLC). This project rebuilds their sample from the same records, checks which of their estimates reproduce, and then asks whether the headline numbers survive three design choices: controls that the policy itself moves, a log outcome that drops hours with no trips, and fare groups defined by fares the policy raised.

The plan is [docs/design.md](docs/design.md), written before any trip records were downloaded, with every later change and its reason in the Amendments. The replication report is [docs/replication.md](docs/replication.md).

## Results so far

The data are 201,868,624 Uber and Lyft trips in January to May of 2024 and 2025, aggregated with DuckDB into origin-destination (OD) cells by date and hour. A separate PySpark build from the raw files gives the same 142,267,997 cells with identical sums.

- **Sample.** The records give the paper's 65,116 OD pairs and 11,020,491 OD-date cells exactly.
- **Outcome.** The paper's equation states log(trips), but its estimates are matched by log(1 + trips). With that outcome, the January hourly series reproduce for both companies in all 24 hours, and 12 of the 13 distance and fare bins reproduce.
- **February to May.** These series do not reproduce: ours are lower in every hour, by 0.011 to 0.017 on average, and neither other period definitions nor other zone lists closed the gap.
- **Controls the policy moves (Part B1).** Dropping the average fare, duration and wait time from the model changes the trip-weighted effect by at most 0.0011, for example from -0.0264 to -0.0257 for all trips over January to May.
- **Fare groups fixed before the policy (Part B3).** The paper groups trips by their own fare, which the charge raised, and reports an effect of -0.366 for trips under $10 (our replication gives -0.448). Grouping each OD pair and hour by its 2024 median fare instead, the lowest group's effect is -0.072 (95% CI -0.083 to -0.061), so most of the paper's estimate reflects trips moving into higher fare groups. This was the pre-registered prediction.

Part B2, the Poisson fit with zero cells, is set up as a cluster run in `msi/` (168 fits over 1.3 billion rows) and has not been run yet. Parts B4, B5 and C (treatment by the charge itself, other clustering, and the longer horizon through August 2026) are not done.

## Run

With Python 3.12 and the packages duckdb, pandas, numpy, pyfixest and psutil, and for the PySpark check pyspark 3.5 with Java 8, 11 or 17. From the repository root:

```
python scripts/download_tlc.py 2024-01 2026-08
python scripts/aggregate_tlc.py 2024-01 2026-08
python scripts/check_data.py 2024-01 2026-08
python scripts/aggregate_spark.py 2024-01 2024-05 2025-01 2025-05
python scripts/replicate_hourly.py --company uber --period jan --outcome log1p --out results/replication/hourly_log1p.csv
python scripts/compare_targets.py results/replication/hourly_log1p.csv
python scripts/replicate_bins.py --outcome log1p log
python scripts/replication_checks.py
python scripts/reanalysis.py --company uber --period janmay --out results/reanalysis/b1
python scripts/reanalysis_b3.py
```

The monthly trip files are about 500 MB each and are not in the repository. The hourly script fits one company and period per call; [docs/replication.md](docs/replication.md) lists the seven series and the other options. On a laptop with 16 GB of memory, the DuckDB aggregation and the PySpark check each take about 20 seconds per month, and the seven hourly series 13 to 15 minutes of fitting for each outcome.

## Data

TLC High Volume For-Hire Vehicle trip records, published by the NYC Taxi and Limousine Commission on NYC Open Data. The paper's estimates in `docs/targets_zhang2026_*.csv` are transcribed from its Tables A.1 and A.2: Zhang, Y., Sang, Y. and Wu, M. (2026). Congestion pricing in New York City: effects on ride-hailing and transit. Transportation Research Part A 208, 104966. https://doi.org/10.1016/j.tra.2026.104966

The code is under the MIT license.

Can Zhang, zhan8639@umn.edu
