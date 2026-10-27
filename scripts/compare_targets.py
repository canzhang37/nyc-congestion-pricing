# hourly estimates vs Table A.2
# rule: 20 of 24 inside, mean |diff| < 0.005
import sys
from pathlib import Path

import pandas as pd

r = pd.read_csv(sys.argv[1])
t = pd.read_csv("docs/targets_zhang2026_tableA2.csv").set_index("hour")
rows = []
for (co, per, outcome, zones), g in r.groupby(["company", "period", "outcome", "zones"], sort=False):
    key = "all_rh" if co == "all" else f"{co}_{per}"
    g = g.set_index("hour").sort_index()
    inside = g.estimate.between(t[key + "_lo"], t[key + "_hi"]).sum()
    diff = g.estimate - t[key]
    rows.append({"company": co, "period": per, "outcome": outcome, "zones": zones, "target": key,
                 "hours_inside": inside, "mean_abs_diff": round(diff.abs().mean(), 4),
                 "mean_diff": round(diff.mean(), 4), "replicates": inside >= 20 and diff.abs().mean() < 0.005})
out = pd.DataFrame(rows)
print(out.to_string(index=False))
out.to_csv(Path(sys.argv[1]).with_name(Path(sys.argv[1]).stem + "_vs_paper.csv"), index=False)
