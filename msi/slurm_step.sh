#!/bin/bash
# one B2 step: prep, smoke, job or merge
set -euo pipefail
cd "${ROOT:?}"
PY=${PY:-$ROOT/.venv/bin/python}
export PYTHONPATH="$ROOT/scripts"
# thread limits for numeric libraries
export RAYON_NUM_THREADS=${SLURM_CPUS_PER_TASK:-4} OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

case "$STEP" in
  prep)
    "$PY" scripts/aggregate_tlc.py 2024-01 2024-05
    "$PY" scripts/aggregate_tlc.py 2025-01 2025-05
    n=$(ls data/agg/cells_2024-0[1-5].parquet data/agg/cells_2025-0[1-5].parquet | wc -l)
    [ "$n" -eq 10 ] || { echo "expected 10 monthly cell files, found $n"; exit 1; }
    echo "- end"
    ;;
  smoke)
    rm -rf output_smoke && mkdir -p output_smoke
    "$PY" scripts/reanalysis.py --company uber --period jan --hours 17-18 --poisson --out output_smoke/b2
    "$PY" msi/b2_tools.py smoke | tee output_smoke/smoke.txt
    echo "- end"
    ;;
  job)
    read -r CO PER < <(sed -n "${SLURM_ARRAY_TASK_ID}p" msi/jobs.txt)
    echo "task $SLURM_ARRAY_TASK_ID: $CO $PER"
    mkdir -p output
    # rerun starts the series afresh
    rm -f "output/b2_${CO}_${PER}_hourly.csv" "output/b2_${CO}_${PER}_summary.csv"
    "$PY" scripts/reanalysis.py --company "$CO" --period "$PER" --poisson --out "output/b2_${CO}_${PER}"
    echo "- end"
    ;;
  merge)
    "$PY" msi/b2_tools.py merge
    ;;
  *)
    echo "unknown STEP $STEP"; exit 1
    ;;
esac
