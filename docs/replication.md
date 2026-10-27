# Replication of Zhang, Sang and Wu (2026)

Congestion charges change what trips cost, and ride-hail trips show the response directly, as the city receives a record of every trip. On January 5, 2025, New York began charging $1.50 for each Uber and Lyft trip that travels to, from, within or through Manhattan south of 60th Street. This report concerns whether the public trip records of the NYC Taxi and Limousine Commission (TLC) reproduce the estimates of Zhang, Sang and Wu (2026), who measured the effect of this charge on ride-hail trips with two-way fixed effects regressions. It is Part A of the pre-registered design in [design.md](design.md), and Parts B and C start from the fits reported here.

The public records reproduce the paper's sample exactly. They also reproduce its January estimates in every hour for both companies, and 12 of its 13 estimates by trip distance and fare, with two settings that differ from the paper's description. The outcome is log(1 + trips), although the paper's equation states log(trips), and the distance and fare bins are fit on a panel of OD pairs by date with the hours of each day summed, which the paper does not specify. The hourly series for February to May and for January to May do not replicate. Our estimates are lower than the paper's in every hour, and none of the other samples, zone lists or covariate sets that we tried closes the gap. The one bin that does not replicate holds the trips with a base fare under $10.

| Target in the paper | Replicates | Result |
| --- | --- | --- |
| Sample size (Section 3.1) | Yes | Same number of OD pairs and of OD-date cells |
| Table 1, four cells of one OD pair | Yes | All values match to the digits shown |
| Table A.2, January, Uber and Lyft | Yes | 24 of 24 hours inside the paper's intervals |
| Table A.2, February to May, Uber and Lyft | No | 0 of 24 hours inside, ours lower in every hour |
| Table A.2, January to May, Uber, Lyft and combined | No | 0 of 24 hours inside, ours lower in every hour |
| Table A.1, six distance bins | Yes | 6 of 6 inside the paper's intervals |
| Table A.1, seven fare bins | 6 of 7 | The $0 to $10 bin does not replicate |

## Data and model

The data are the TLC high-volume for-hire vehicle records for January to May of 2024 and 2025, restricted to Uber (license HV0003) and Lyft (HV0005). We aggregate the trips by pickup zone, dropoff zone, pickup date and pickup hour, and we keep the sums of trips, miles, seconds, base fare and wait time in each cell, from which the cell averages follow. An OD pair is treated from January 5, 2025 if its pickup or dropoff zone is one of 38 Manhattan zones: the 36 zones where at least 95% of intra-zone trips carry the charge, and Financial District South and Battery Park, which lie south of 60th Street but fall below that threshold (design amendment 2).

The cells are built with DuckDB (`scripts/aggregate_tlc.py`). A separate PySpark build from the raw files (`scripts/aggregate_spark.py`, design amendment 9) gives the same 142,267,997 cells for the ten months, from 201,868,624 trips, with every integer sum equal and every float sum identical (`results/checks/spark_vs_duckdb.csv`).

For each hour of the day, the model regresses the outcome on the treatment indicator and the cell's average trip distance, duration, base fare and wait time, with OD-pair and date fixed effects and standard errors clustered by OD pair. The paper fits it with PanelOLS from the Python package linearmodels. We use `feols` from pyfixest and keep singleton cells, as PanelOLS does. The pre-registered criterion is that an hourly series replicates if at least 20 of its 24 estimates lie inside the paper's 95% intervals and the mean absolute difference over hours is below 0.005. A distance or fare bin replicates if its estimate lies inside the paper's interval or within 0.01 of the paper's estimate.

## Sample

The records give the paper's 65,116 OD pairs and its 11,020,491 observations exactly. The paper describes these observations as hourly, but 11,020,491 is the number of OD-date cells with at least one trip. The OD-date-hour cells, on which the hourly model is fit, number 70,005,446.

The paper's Table 1 lists four cells of the OD pair from the Garment District (zone 100) to Newark Airport (zone 1) at 8:00, on January 1 and 2, 2024 and May 30 and 31, 2025. Our cells have the same trip counts and the same average miles, duration, base fare and wait time to the two decimals shown. The counts show that the paper's cells combine Uber and Lyft trips, and the averages are consistent with trips dated by pickup time and waits measured from request to pickup, which is how we build our cells.

## Hourly effects

Table 2 compares our hourly estimates with Table A.2 of the paper under both outcomes. With log(1 + trips), the two January series replicate: every hourly estimate lies inside the paper's interval and differs from the paper's estimate by 0.0002 or less on average. With log(trips), each January series has only 2 of 24 hours inside the paper's intervals. We conclude that the paper fit log(1 + trips). The two outcomes give different magnitudes. The log(trips) estimates are 1.3 to 1.6 times the log(1 + trips) estimates (median over hours in each series), as adding 1 to each count shrinks proportional changes in cells with few trips.

**Table 2.** Hours inside the paper's 95% intervals and mean absolute difference from the paper over the 24 hours.

| Series | log(1 + trips): hours inside | Mean absolute difference | log(trips): hours inside | Mean absolute difference |
| --- | ---: | ---: | ---: | ---: |
| Uber, January | 24 | 0.0002 | 2 | 0.0131 |
| Lyft, January | 24 | 0.0001 | 2 | 0.0154 |
| Uber, February to May | 0 | 0.0166 | 0 | 0.0311 |
| Lyft, February to May | 0 | 0.0135 | 0 | 0.0127 |
| Uber, January to May | 0 | 0.0161 | 0 | 0.0302 |
| Lyft, January to May | 0 | 0.0108 | 6 | 0.0074 |
| Combined, January to May | 0 | 0.0169 | 0 | 0.0260 |

The five series that involve February to May do not replicate under either outcome. With log(1 + trips), our estimate is below the paper's in every hour of every one of these series, by 0.011 to 0.017 on average. The difference has the same sign for both companies, although the paper's Lyft estimates are positive in all 24 hours of February to May and its Uber estimates are negative in 23. It is therefore not a rescaling of the effects.

We tried several explanations at 18:00 (Table 3). Other treated zone lists, from the 36 zones of the 95% rule to all of Manhattan, move the Uber estimate by at most 0.005, and every estimate stays below the paper's -0.0315 by at least 0.013. Other readings of the February to May fit, with all of January to May 2024 as the comparison or with separate January and February to May indicators in one January to May fit, change the estimates by less than 0.006. Fits for single months show that the effect varies from month to month, but no single month puts both companies inside the paper's intervals. The covariates do not explain the gap either: dropping all four moves the log(trips) estimate for Uber from -0.0675 to -0.0671.

**Table 3.** Estimates at 18:00 under other samples and zone lists, with log(1 + trips) and the paper's covariates.

| Check | Uber | Lyft | Paper (Uber, Lyft) |
| --- | ---: | ---: | --- |
| February to May, as in Table 2 | -0.0474 | 0.0101 | -0.0315, 0.0265 |
| February to May against January to May 2024 | -0.0530 | 0.0119 | -0.0315, 0.0265 |
| Separate January and February to May indicators | -0.0505 | 0.0119 | -0.0315, 0.0265 |
| February only | -0.0476 | 0.0119 | -0.0315, 0.0265 |
| March only | -0.0320 | 0.0006 | -0.0315, 0.0265 |
| April only | -0.0408 | 0.0205 | -0.0315, 0.0265 |
| May only | -0.0753 | 0.0095 | -0.0315, 0.0265 |
| January to May, 38 zones | -0.0498 | | -0.0315 |
| January to May, 36 zones | -0.0502 | | -0.0315 |
| January to May, crossing zones treated | -0.0490 | | -0.0315 |
| January to May, Yellow Zone of the TLC lookup | -0.0485 | | -0.0315 |
| January to May, all of Manhattan | -0.0452 | | -0.0315 |

We cannot tell from the records why the later months differ. The January and February to May fits use the same data, zones, covariates and code, and the January fits differ from the paper's by 0.0002 or less on average. In the paper's Table A.2, the Uber columns for January to May and for February to May are identical in all 24 hours, which suggests that at least one column was copied in error. The remaining difference may come from a different data extract or code for the later months. The paper states that its data are available on request, and the authors' extract or code would settle the question.

## Distance and fare bins

Table A.1 of the paper gives one estimate for each distance bin and each fare bin, and the paper does not say how the 24 hours are pooled. Fits on the OD-date panel, with the trips of each OD pair in the bin summed over the day, reproduce the paper's estimates. The mean of 24 hourly fits does not: for trips under 1 mile it is -0.044, against the paper's -0.097. The OD-date panel is also the panel whose size the paper reports. Trips are binned by their own distance and base fare, as the paper describes.

**Table 4.** Estimates by bin with log(1 + trips) on the OD-date panel, with 95% intervals.

| Bin | Ours | Paper | Inside |
| --- | --- | --- | --- |
| 0 to 1 mile | -0.103 (-0.111, -0.095) | -0.097 (-0.105, -0.089) | Yes |
| 1 to 2 miles | -0.093 (-0.099, -0.087) | -0.089 (-0.095, -0.083) | Yes |
| 2 to 5 miles | -0.062 (-0.067, -0.058) | -0.063 (-0.068, -0.059) | Yes |
| 5 to 10 miles | -0.038 (-0.041, -0.035) | -0.038 (-0.041, -0.035) | Yes |
| 10 to 20 miles | -0.014 (-0.016, -0.012) | -0.014 (-0.016, -0.012) | Yes |
| 20 miles or more | -0.010 (-0.016, -0.004) | -0.010 (-0.016, -0.004) | Yes |
| $0 to $10 | -0.448 (-0.464, -0.433) | -0.366 (-0.376, -0.356) | No |
| $10 to $15 | -0.150 (-0.160, -0.139) | -0.141 (-0.150, -0.132) | Yes |
| $15 to $20 | -0.093 (-0.100, -0.085) | -0.089 (-0.095, -0.082) | Yes |
| $20 to $25 | -0.016 (-0.021, -0.011) | -0.017 (-0.022, -0.013) | Yes |
| $25 to $30 | -0.044 (-0.048, -0.040) | -0.044 (-0.048, -0.040) | Yes |
| $30 to $35 | -0.002 (-0.006, 0.001) | -0.004 (-0.007, -0.000) | Yes |
| $35 or more | 0.023 (0.021, 0.025) | 0.023 (0.020, 0.025) | Yes |

The $0 to $10 bin is the only bin that does not replicate. Recomputing it from the trip records gives the same estimate, and dropping trips with a zero or negative base fare moves it further from the paper's, to -0.481. Binning on the base fare less the charge, in case the paper removed the charge from the fare, puts only one of the seven fare bins inside the paper's intervals. That check also shows how strongly the fare bins depend on where each trip falls: subtracting the $1.50 charge from the fares of charged trips turns the estimate for the lowest bin from -0.448 to 0.145. A charge that raises fares moves trips from lower to higher bins, and Part B3 refits the fare bins with groups fixed before the policy for this reason. With log(trips), 7 of the 13 bins replicate under the design's rule.

## Zone list

The zone list does not change the replication results. With the 36 zones of the 95% rule, or with the OD pairs that touch the six zones crossing 60th Street dropped, no hourly estimate moves by more than 0.003, and the January series still replicate. The 38 zones are the closest to the paper: the mean absolute difference for the January series is 0.0002 for Uber and 0.0001 for Lyft with 38 zones, 0.0005 and 0.0002 with 36 zones, and 0.0006 and 0.0013 without the crossing zones.

## What Parts B and C use

Parts B and C start from the settings that reproduce the paper: log(1 + trips), the 38 zones, hourly fits on OD-date-hour cells, and bin fits on the OD-date panel. Changes to these settings, such as the Poisson fit with zero cells in B2, are compared with the fits in this report.

## Files and commands

| File | Contents |
| --- | --- |
| `results/checks/panel_size.csv` | Sample counts against the paper |
| `results/replication/table1_cells.csv` | The four cells of the paper's Table 1 |
| `results/replication/hourly_log1p.csv`, `hourly_log.csv` | Hourly estimates for the seven series under each outcome |
| `results/replication/hourly_log1p_zones36.csv`, `hourly_log1p_nocrossing.csv` | The same with the other zone lists |
| `results/replication/*_vs_paper.csv` | Each series scored against Table A.2 |
| `results/replication/bins.csv` | Distance and fare bins under each outcome, scored against Table A.1 |
| `results/replication/diagnostics.csv` | The checks in Table 3 and in the bin section |
| `docs/targets_zhang2026_tableA2.csv`, `targets_zhang2026_tableA1.csv` | Targets transcribed from the paper |

The trip records are not in the repository. These commands rebuild every result from the repository root, with Python 3 and the packages duckdb, pandas, numpy, pyfixest and psutil. The hourly script fits one company and period per call. The seven series are Uber and Lyft in each of the three periods (`--period jan`, `febmay` or `janmay`) and all trips in January to May (`--company all`). The log(trips) series and the zone-list checks add `--outcome log`, `--zones36` or `--drop-crossing`, each with its own output file.

```
python scripts/download_tlc.py 2024-01 2026-08
python scripts/aggregate_tlc.py 2024-01 2026-08
python scripts/check_data.py 2024-01 2026-08
python scripts/replicate_hourly.py --company uber --period jan --outcome log1p --out results/replication/hourly_log1p.csv
python scripts/compare_targets.py results/replication/hourly_log1p.csv
python scripts/replicate_bins.py --outcome log1p log
python scripts/replication_checks.py
```

On a laptop with 16 GB of memory, the seven series take 13 to 15 minutes of fitting for each outcome.

## References

Zhang, Y., Sang, Y. and Wu, M. (2026). Congestion pricing in New York City: effects on ride-hailing and transit. Transportation Research Part A 208, 104966. https://doi.org/10.1016/j.tra.2026.104966

NYC Taxi and Limousine Commission. Data dictionary, High Volume FHV trip records (March 18, 2025).
