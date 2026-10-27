# Design: New York's congestion charge and ride-hail trips

This plan was written after reading Zhang, Sang and Wu (2026) and before any trip records were downloaded. Changes made after the trip records are opened go in the Amendments section, with a reason. The paper's results are public, which makes Part A a replication with known targets. Parts B and C go beyond the paper.

## Questions

1. Replication (Part A). Do the public trip records reproduce the hourly estimates of Zhang, Sang and Wu (2026) for the effect of the January 5, 2025 per-trip charge on Uber and Lyft trips?
2. Reanalysis (Part B). Do the headline numbers change under three design choices that the paper made: controls that the policy itself moves, a log outcome that drops hours with no trips, and fare groups defined by fares the policy raised?
3. Longer horizon (Part C). What happened through August 2026? The paper covers January to May 2025 and names the short window as its first limitation.

## The policy

- On January 5, 2025, New York started the Central Business District Tolling Program. High-volume for-hire vehicles (Uber, Lyft) pay $1.50 for each trip that travels to, from, within or through the Congestion Relief Zone, Manhattan south of 60th Street, and taxis pay $0.75. Pooled trips pay per passenger, and there is no daily cap.
- During January 2025 Uber showed the charge as an add-on to the fare, while Lyft gave a matching $1.50 credit, redeemable the following week. The paper uses this difference to separate the two platforms.
- Private cars pay $9 at peak with E-ZPass. The New York State congestion surcharge on trips below 96th Street applies before and after the start date.

Source: Section 2 of Zhang, Sang and Wu (2026). The charge in the data is checked by trip type and hour in `results/checks/fee_by_od_type_hour.csv`.

## What the paper did

- Data: TLC High Volume FHV trip records, January to May of 2024 and 2025, aggregated to origin-destination (OD) pairs of taxi zones by date and hour. Only cells with at least one trip enter: 65,116 OD pairs and 11,020,491 OD-date-hour observations.
- Treatment: the indicator is 1 from January 5, 2025 for OD pairs with the pickup or the dropoff zone in the zone. All other OD pairs are controls.
- Model (their equation 1), estimated separately for each hour of the day: the log of the trip count on the treatment indicator, with covariates for the average trip distance, duration, base fare and wait time of the cell, OD-pair fixed effects and date fixed effects. OLS, with standard errors clustered by OD pair.
- Heterogeneity: separate fits by trip distance (6 bins) and by the trip's own base fare (7 bins). Economic outcomes: base fare, driver pay and platform revenue, with the fare covariate removed.
- Robustness: Manhattan-only trips, and a 1 km buffer around the zone with nearby control trips dropped.

## Data

- Trip records: TLC High Volume FHV monthly Parquet files, January 2024 to August 2026 (32 files of 490 to 510 MB). Fields used: company license (Uber HV0003, Lyft HV0005), request, pickup and dropoff times, pickup and dropoff zones, trip miles and seconds, base passenger fare, driver pay, `cbd_congestion_fee`.
- Zones: the TLC zone lookup and zone shapes. A zone is in the Congestion Relief Zone if it is in Manhattan and at least 95% of its post-policy intra-zone trips carry the charge. The list is compared with the zones south of 60th Street on the map, and any difference is reported.
- Processing: DuckDB reads only the needed columns and writes aggregates by OD pair, date, hour and company: trips, trips charged, mean miles, mean seconds, mean base fare, mean wait (request to pickup), total base fare and total driver pay. Row-level records are not committed.
- Checks before any outcome is analyzed: every month present, `cbd_congestion_fee` zero before January 5, 2025, its values after that date by OD type and hour, and the share of charged trips with neither endpoint in the zone (trips through the zone).

## Part A: replication

- Sample, model and clustering as in the paper (above), for Uber, Lyft and both together, January to May of 2024 and 2025.
- Targets: Table A.2 (hourly effects with 95% intervals for Lyft and Uber over January to May, January only and February to May, and all ride-hail), saved in `docs/targets_zhang2026_tableA2.csv`, and Table A.1 (distance and fare bins).
- Criterion: a series replicates if its estimate lies inside the paper's 95% interval in at least 20 of the 24 hours and the mean absolute difference over hours is below 0.005. A distance or fare bin replicates if its estimate lies inside the paper's interval or within 0.01 of the paper's estimate. Otherwise the differences in sample size, zone list and data revisions are reported.
- Known issue: in Table A.2 the Uber columns for January to May and for February to May are identical in all 24 hours, including the intervals. The replication reports both estimates.

## Part B: reanalysis

Each change is made alone, then all together, on the Part A sample. For each series the summary is the average of the hourly effects weighted by 2024 trips in that hour, with a 95% interval.

1. No post-treatment controls. Average fare, duration and wait time respond to the policy (the paper reports fare increases of up to 14%), and controlling for them removes part of the effect. Refit without covariates.
2. Zero cells. The log outcome keeps only OD-date-hour cells with trips. Refit by Poisson pseudo-likelihood with the same fixed effects on the full grid of OD pairs seen in both years, with zero counts included. The effect is reported as exp(theta) - 1.
3. Fare groups fixed before the policy. The paper groups trips by their own base fare, and the policy raised fares, which moves trips from lower to higher groups. Refit with groups defined by the OD pair's 2024 median base fare in that hour. Prediction to be tested: the decline for the lowest fare group is smaller than the paper's 36.6%.
4. Treatment by the charge itself. Classify an OD pair as treated if at least half of its post-policy trips carry the charge, which also covers trips through the zone, and compare with the endpoint rule.
5. Inference. Standard errors clustered by OD pair (as in the paper), by pickup zone, and two-way by OD pair and date.

## Part C: longer horizon

- Sample: January 2024 to August 2026, all ride-hail trips, by company and combined.
- Model: the Part A model with the treatment indicator split by calendar month after January 5, 2025, without post-treatment controls (B1), giving a monthly path of the effect relative to 2024. The same with the Poisson fit (B2).
- Primary result: the trip-weighted effect over January to August 2026 against that over February to May 2025, for combined ride-hail trips.

## Not in this project

Subway ridership (the paper's MTA origin-destination data), private-car tolls and traffic speeds.

## Amendments

Amendments 1 to 3 were written after the trip records were aggregated and the data checks were run, and before any trip count was compared between treated and control OD pairs.

1. Processing. The date and hour of a trip are those of its pickup time. Cells are stored as sums by OD pair, date, hour, company, distance bin (the paper's 6 bins) and fare bin (the paper's 7 bins of the trip's own base fare), so the main cells and the bin fits come from one table (`scripts/aggregate_tlc.py`). The 2024 files have no `cbd_congestion_fee` column, and the charge is set to zero there. The wait time is the pickup time minus the request time as recorded. About 1% of trips have a pickup before the request, and they are kept.
2. Zone list. On January 5 to May 31, 2025, 36 Manhattan zones have at least 95% of intra-zone trips charged (`results/checks/manhattan_zones.csv`). Two zones at the southern tip fall below the threshold although they lie wholly south of 60th Street: Financial District South (92.2% of 1,099 trips) and Battery Park (3 of 5 trips). The treated zone set is the 36 zones plus these two, and Part A also reports the fit with the 36 zones. Six zones cross 60th Street and have 14% to 50% of intra-zone trips charged: Lincoln Square East and West, Central Park, Upper East Side South, and Lenox Hill East and West. They stay controls, as the rule implies, and Part A also reports the fit with OD pairs that touch them dropped. Part B4, which defines treatment by the charge, covers them.
3. Sample size. The public files reproduce the paper's sample counts exactly: 65,116 OD pairs and 11,020,491 OD-date cells with at least one trip in January to May of 2024 and 2025. The paper describes the 11,020,491 as hourly observations, but the OD-date-hour cells number 70,005,446. Part A uses OD-date-hour cells, as the paper's model is fit by hour, and the replication report states the difference.
4. Outcome (written after the first Part A fits). With log(trips), the hour-18 estimates were far from the paper's (Uber, January to May: -0.068 against -0.032), and neither the covariates nor other zone lists changed them much. With log(1 + trips), the January fits (January 2024 and January 2025) reproduce the paper's Uber and Lyft series: all 24 hourly estimates lie inside the paper's intervals, and the mean absolute difference is 0.0002 or less (`results/replication/`). The paper therefore appears to have fit log(1 + trips), although its equation 1 states log(trips). Part A uses log(1 + trips) and also reports log(trips). With log(trips), no series replicates, and each January series has only 2 of 24 hours inside the paper's intervals. The log(trips) estimates are 1.3 to 1.6 times the log(1 + trips) estimates (median over hours in each series), as adding 1 shrinks proportional changes in cells with few trips. The February to May and January to May series do not replicate. With log(1 + trips), none of the hourly estimates lies inside the paper's interval, and ours are lower in every hour, by 0.011 to 0.017 on average, for both companies and for the combined series. A February to May fit against all of January to May 2024, separate January and February to May indicators in one fit, and single-month fits did not close the gap. Neither did the zone list: with the 36 zones, or with OD pairs that touch the six zones across 60th Street dropped, no hourly estimate moves by more than 0.003, and the January series still replicate.
5. Bin fits (written after the first Table A.1 fits). The paper does not say how the single estimate for a bin pools the 24 hours. Fits on the OD-date panel, with the trips of each OD pair in the bin summed over the day, reproduce the paper's estimates, and the average of 24 hourly fits does not (0 to 1 miles: -0.044 against -0.097). Table A.1 is therefore fit on the OD-date panel, with log(1 + trips) as in amendment 4 (`scripts/replicate_bins.py`). This agrees with amendment 3, as the paper's 11,020,491 observations are OD-date cells. With log(1 + trips), 12 of the 13 bins lie inside the paper's intervals: all six distance bins and six of the seven fare bins. The $0 to $10 bin does not replicate (-0.448 against -0.366). Dropping trips with a zero or negative base fare moves it further away (-0.481), and binning on the base fare less the charge puts only one of the seven fare bins inside the paper's intervals. With log(trips), 7 of the 13 bins replicate under the design's rule.
6. Summary intervals in Part B. The trip-weighted average of the 24 hourly effects needs the covariance between hours, as the same OD pair appears in every hourly fit. Each hourly fit keeps the influence of each OD pair on its treatment estimate, the influences of an OD pair are added across hours with the trip weights, and the variance is their sum of squares times G/(G - 1), where G is the number of OD pairs. This is the OD-clustered variance of the 24 hourly models fit jointly. The difference between two specifications on the same sample, such as B1 against Part A, uses the difference of their influences. The weights are the 2024 trips of the series in each hour. The method was fixed before the B1 fits were run (`scripts/reanalysis.py`), and its hourly estimates and standard errors agree with those of pyfixest to within 0.001%.
7. Part B2 (written before the B2 fits, after two timing fits on single hours). For each series and hour, the grid holds the OD pairs with at least one trip at that hour in both years of the series' sample, crossed with every date of the sample, and a cell with no trip has a count of zero. The covariates are not defined in empty cells, so B2 has none, and its change from Part A combines B1 with the Poisson fit on the grid. B2 is therefore reported against B1, which isolates the Poisson fit with zero cells, and against Part A. The model is a Poisson pseudo-likelihood with OD-pair and date fixed effects and errors clustered by OD pair. The summary is the average of the hourly estimates weighted by 2024 trips, with the interval of amendment 6 built from the Poisson influences, and it is reported as exp(theta) - 1. The 168 fits take an estimated 52 to 106 minutes with up to 5 GB of memory for the largest hour, so they run on MSI.
8. Part B3 (written before the B3 fits). Each OD pair and hour gets the median base fare of its Uber and Lyft trips in January to May 2024, and the median places the pair-hour in one of the paper's seven fare groups. OD pairs and hours without a trip in 2024 have no group and are left out. As in Table A.1 (amendment 5), the fit for a group is on a daily panel, with the trips of each OD pair in the group's hours summed over the day, the cell averages of the four covariates, log(1 + trips), OD-pair and date fixed effects, and errors clustered by OD pair. The prediction is tested on the lowest group. It is confirmed if the 95% interval lies above -0.366, the paper's estimate, rejected if the interval lies below it, and undecided otherwise. The lowest group is also compared with our replication of the paper's lowest bin (-0.448).
9. PySpark check (written before the Spark run). The cell aggregation of amendment 1 is rebuilt with PySpark from the raw files for the ten analysis months (January to May of 2024 and 2025), written apart from the DuckDB code, and compared cell by cell with `data/agg/` (`scripts/aggregate_spark.py`). The check passes if both give the same set of cells, the same integer sums in every cell (trips, charged trips, trip seconds, wait seconds, shared requests), and float sums (charge, miles, base fare, driver pay) that agree to a relative 1e-6, the rounding of the stored float32 sums. If it fails, the cause is traced before any result that uses the cells is reported again.

The other checks gave the expected results (`results/checks/`). All 32 months are present with every calendar day. Before January 5, 2025 the only charged trips are 1,184 picked up on January 4 after 22:00 and dropped off after midnight. From January 2025 to August 2026 the charge per charged trip averages $1.50 in every month, and at least 98.8% of intra-zone trips are charged in each month. Of the charged trips on January 5 to May 31, 2025, 6.0% have neither end in the 36 zones.

## References

- Zhang, Y., Sang, Y. and Wu, M. (2026). Congestion pricing in New York City: effects on ride-hailing and transit. Transportation Research Part A 208, 104966. https://doi.org/10.1016/j.tra.2026.104966
- NYC Taxi and Limousine Commission. Data dictionary, High Volume FHV trip records (March 18, 2025).
