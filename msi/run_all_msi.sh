#!/bin/bash
# Part B2 on MSI: Poisson fits with zero cells
# usage and settings: msi/README.md
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
MODE=${1:-run}
USER=${USER:-$(whoami)}
EMAIL=${EMAIL:-${USER}@umn.edu}
ACCOUNT=${ACCOUNT:-}
PARTITION=${PARTITION:-msismall}
DRYRUN=${DRYRUN:-0}
NJOBS=$(grep -c . msi/jobs.txt)
die() { echo "ERROR: $*" >&2; exit 1; }

if [ "$MODE" = "setup" ]; then
  if [ -n "${PY_MODULE:-}" ]; then module load "$PY_MODULE" || die "cannot load $PY_MODULE"
  else module load python3 2>/dev/null || true; fi
  PY=$(command -v python3) || die "no python3; set PY_MODULE (see: module avail python)"
  "$PY" -c 'import sys; assert (3, 10) <= sys.version_info[:2] <= (3, 12), sys.version' \
    || die "need Python 3.10-3.12; set PY_MODULE (see: module avail python)"
  "$PY" -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r msi/requirements.txt
  (cd scripts && ../.venv/bin/python -c "import reanalysis, pyfixest; print('pyfixest', pyfixest.__version__, 'ok')")
  echo "setup done"
  exit 0
fi

[ -e .venv/bin/python ] || die "run 'bash msi/run_all_msi.sh setup' first"

if [ "$MODE" = "data" ]; then
  command -v curl > /dev/null || die "curl not found"
  .venv/bin/python scripts/download_tlc.py 2024-01 2024-05
  .venv/bin/python scripts/download_tlc.py 2025-01 2025-05
  echo "data done: $(ls data/raw/*.parquet | wc -l) files in data/raw"
  exit 0
fi

if [ "$MODE" = "status" ]; then
  echo "cell files: $(ls data/agg/cells_*.parquet 2>/dev/null | wc -l)/10"
  [ -f output_smoke/smoke.txt ] && cat output_smoke/smoke.txt
  echo "finished series: $(ls output/b2_*_summary.csv 2>/dev/null | wc -l)/$NJOBS"
  squeue -u "$USER" -o "%.12i %.18j %.8T %.10M %.20R" || true
  for f in $(ls -t logs/*.out 2>/dev/null | head -3); do echo "== $f"; tail -3 "$f"; done
  exit 0
fi

mkdir -p logs
COMMON=(--chdir="$ROOT" --mail-user="$EMAIL" --mail-type=FAIL --kill-on-invalid-dep=yes --parsable --partition="$PARTITION")
if [ -n "$ACCOUNT" ]; then COMMON+=(--account="$ACCOUNT"); fi

submit() {  # prints the job id
  if [ "$DRYRUN" = "1" ]; then echo "sbatch $*" >&2; echo "DRY$RANDOM"; else sbatch "$@"; fi
}
step() {  # step name, then sbatch options
  local s=$1; shift
  submit "${COMMON[@]}" "$@" --job-name="nyc_b2_$s" --export="ALL,ROOT=$ROOT,STEP=$s" msi/slurm_step.sh
}
merge_job() {  # after all array tasks, failed included
  step merge --dependency=afterany:"$1" --cpus-per-task=1 --mem=4G --time=00:15:00 \
    --mail-type=END,FAIL --output=logs/merge_%j.out
}

case "$MODE" in
  run)
    ls data/raw/fhvhv_tripdata_2024-0[1-5].parquet data/raw/fhvhv_tripdata_2025-0[1-5].parquet > /dev/null 2>&1 \
      || die "raw files missing; run 'bash msi/run_all_msi.sh data' first"
    P=$(step prep --cpus-per-task=4 --mem=16G --time=01:00:00 --output=logs/prep_%j.out)
    S=$(step smoke --dependency=afterok:"$P" --cpus-per-task=4 --mem=8G --time=00:30:00 --output=logs/smoke_%j.out)
    A=$(step job --dependency=afterok:"$S" --cpus-per-task=4 --mem=24G --time=02:00:00 \
        --array=1-"$NJOBS" --output=logs/b2_%A_%a.out)
    M=$(merge_job "$A")
    echo "prep $P -> smoke $S -> array $A ($NJOBS tasks) -> merge $M"
    ;;
  rerun)
    A=$(step job --cpus-per-task=4 --mem=24G --time=02:00:00 --array=1-"$NJOBS" --output=logs/b2_%A_%a.out)
    M=$(merge_job "$A")
    echo "array $A ($NJOBS tasks) -> merge $M"
    ;;
  merge)
    M=$(step merge --cpus-per-task=1 --mem=4G --time=00:15:00 --output=logs/merge_%j.out)
    echo "merge $M"
    ;;
  *)
    die "unknown mode $MODE"
    ;;
esac
echo "check with: bash msi/run_all_msi.sh status"
