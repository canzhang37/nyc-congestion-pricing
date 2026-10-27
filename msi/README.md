# Part B2 on MSI

Part B2 fits the hourly model by Poisson pseudo-likelihood on the grid of OD pairs and dates with zero cells (design amendment 7). The 168 fits hold 1.3 billion rows in all and need up to 5 GB each, which is more than the laptop has. The bundle runs them on MSI and returns two small result files.

## Steps

From a login node, in the unpacked bundle folder:

```
bash msi/run_all_msi.sh setup
bash msi/run_all_msi.sh data
bash msi/run_all_msi.sh
bash msi/run_all_msi.sh status
```

`setup` builds a Python virtual environment from `msi/requirements.txt`. `data` downloads the ten monthly high-volume FHV files for January to May of 2024 and 2025 from the TLC site (about 4.9 GB) with `scripts/download_tlc.py`. The last command submits four steps, each started only if the one before it succeeded: a job that aggregates the files into `data/agg` with `scripts/aggregate_tlc.py`, a smoke test, an array of seven tasks (one per series in `msi/jobs.txt`), and a merge job.

The smoke test fits Uber in January at 17:00 and 18:00 and checks that the Part A and B1 estimates equal the committed laptop fits in `results/reanalysis/b1_hourly.csv`. Equal estimates show that MSI rebuilt the same cells from the trip records.

## Resources

Each array task uses 4 cores and at most 24 GB for 5 to 40 minutes, about 10 core-hours in all. The prep job takes about 5 minutes. `EMAIL`, `ACCOUNT`, `PARTITION` and `PY_MODULE` can be set before a command, as the header of `msi/run_all_msi.sh` describes.

## Results

The merge job writes `nyc_b2_results_<date>.zip` in the bundle root, with `results/reanalysis/b2_hourly.csv`, `results/reanalysis/b2_summary.csv`, `STATUS.txt` and the smoke check. Only this zip comes back to the laptop. If `STATUS.txt` lists unfinished series, `bash msi/run_all_msi.sh rerun` runs the array and the merge again.
