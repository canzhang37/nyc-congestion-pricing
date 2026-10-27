# B2 cluster run: smoke check and merge
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd

JOBS = [line.split() for line in Path("msi/jobs.txt").read_text().splitlines() if line.strip()]


def smoke():
    t = pd.read_csv("output_smoke/b2_hourly.csv")
    ref = pd.read_csv("results/reanalysis/b1_hourly.csv")
    m = t.merge(ref, on=["company", "period", "spec", "hour"], suffixes=("", "_ref"))
    # A and B1 must match the laptop fits
    assert len(m) == 4, f"expected 4 matching A/B1 rows, got {len(m)}"
    diff = (m.estimate - m.estimate_ref).abs().max()
    assert diff < 1e-10, f"A/B1 differ from the committed fits by {diff}"
    assert (t.spec == "B2").sum() == 2, "B2 missing"
    print(f"smoke ok: A and B1 equal the committed fits (max difference {diff:.1e}), B2 fitted at 2 hours")


def merge():
    out = Path("results/reanalysis")
    out.mkdir(parents=True, exist_ok=True)
    status, hourly, summary = [], [], []
    for co, per in JOBS:
        h, s = Path(f"output/b2_{co}_{per}_hourly.csv"), Path(f"output/b2_{co}_{per}_summary.csv")
        if not (h.exists() and s.exists()):
            status.append(f"{co} {per}: not finished")
            continue
        hh, ss = pd.read_csv(h), pd.read_csv(s)
        # 24 hours x specs and differences
        ok = len(hh) == 72 and len(ss) == 6
        status.append(f"{co} {per}: {'ok' if ok else f'incomplete ({len(hh)} hourly rows, {len(ss)} summary rows)'}")
        hourly.append(hh)
        summary.append(ss)
    if hourly:
        pd.concat(hourly).to_csv(out / "b2_hourly.csv", index=False)
        pd.concat(summary).to_csv(out / "b2_summary.csv", index=False)
    done = sum(x.endswith(": ok") for x in status)
    text = f"B2 collected {datetime.now():%Y-%m-%d %H:%M}\nseries: {len(JOBS)}, finished: {done}\n" + "\n".join(status) + "\n"
    if done < len(JOBS):
        text += "To rerun the unfinished series: bash msi/run_all_msi.sh rerun\n"
    Path("STATUS.txt").write_text(text)
    print(text)
    name = f"nyc_b2_results_{datetime.now():%Y%m%d_%H%M}.zip"
    with zipfile.ZipFile(name, "w", zipfile.ZIP_DEFLATED) as z:
        for f in [out / "b2_hourly.csv", out / "b2_summary.csv", Path("STATUS.txt"), Path("output_smoke/smoke.txt")]:
            if f.exists():
                z.write(f, f.as_posix())
    print(f"packed {name}")


if __name__ == "__main__":
    {"smoke": smoke, "merge": merge}[sys.argv[1]]()
