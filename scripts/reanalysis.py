# Part B refits and trip-weighted summaries
import argparse
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pyfixest as pf
from pyfixest.estimation import demean

import replicate_hourly as rh

COVS = ["avg_miles", "avg_time", "avg_fare", "avg_wait"]
# A: Part A model; B1: no post-policy covariates
SPECS = {"A": COVS, "B1": []}


def hourly(df):
    """Fit every spec on one hour. The two-way demeaning is done once, and each
    spec's treatment estimate gets its influence per OD pair for the pooled interval."""
    y = np.log1p(df.trips.to_numpy(float))
    cols = np.column_stack([y, df.treat.to_numpy(float)] + [df[c].to_numpy(float) for c in COVS])
    fe = np.column_stack([pd.factorize(df.od)[0], pd.factorize(df.date)[0]]).astype(np.uint64)
    z, ok = demean(cols, fe, np.ones(len(df)), tol=1e-8)
    assert ok, "demeaning did not converge"
    od = df.od.to_numpy()
    n_od, n_date = len(np.unique(od)), int(fe[:, 1].max()) + 1
    out = {}
    for name, covs in SPECS.items():
        x = z[:, [1] + [2 + COVS.index(c) for c in covs]]
        xtx_inv = np.linalg.inv(x.T @ x)
        beta = xtx_inv @ (x.T @ z[:, 0])
        e = z[:, 0] - x @ beta
        score = pd.DataFrame(x * e[:, None]).groupby(od).sum().to_numpy()
        psi = pd.Series(score @ xtx_inv[0], index=np.unique(od))
        # CRV1 factors as in pyfixest
        k = x.shape[1] + n_date - 1
        c = n_od / (n_od - 1) * (len(y) - 1) / (len(y) - k)
        out[name] = {"estimate": beta[0], "se": np.sqrt(c * (psi ** 2).sum()), "psi": psi}
    return out


def grid(con, hour, company, period, zones):
    """B2 sample: OD pairs with trips at this hour in both years, crossed with every
    date of the sample, with zero where no trip occurred (design amendment 7)."""
    dates = pd.concat([pd.Series(pd.date_range(a, b)) for a, b in rh.PERIODS[period]])
    files = [f"data/agg/cells_{m}.parquet" for m in sorted(set(dates.dt.strftime("%Y-%m")))]
    win = " OR ".join(f"date BETWEEN '{a}' AND '{b}'" for a, b in rh.PERIODS[period])
    cond = "" if company == "all" else f"AND company = '{company}'"
    inz = ", ".join(map(str, zones))
    con.register("dates", pd.DataFrame({"date": dates.dt.date}))
    return con.execute(f"""
        WITH c AS (SELECT pu_zone, do_zone, date, sum(trips) AS trips FROM read_parquet({files})
                   WHERE hour = {hour} AND ({win}) {cond} GROUP BY ALL),
             seen AS (SELECT pu_zone, do_zone FROM c GROUP BY ALL HAVING count(DISTINCT year(date)) = 2)
        SELECT s.pu_zone::INTEGER * 1000 + s.do_zone AS od, d.date, coalesce(c.trips, 0) AS trips,
               ((s.pu_zone IN ({inz}) OR s.do_zone IN ({inz})) AND d.date >= '{rh.START}')::INTEGER AS treat
        FROM seen s CROSS JOIN dates d
        LEFT JOIN c ON c.pu_zone = s.pu_zone AND c.do_zone = s.do_zone AND c.date = d.date""").df()


def poisson(df):
    m = pf.fepois("trips ~ treat | od + date", data=df, vcov={"CRV1": "od"}, fixef_rm="none")
    # OD-pair influence from pyfixest scores
    psi = pd.Series(m._scores[:, 0]).groupby(df.od.to_numpy()).sum() * m._bread[0, 0]
    r = m.tidy().loc["treat"]
    assert np.isclose(np.sqrt(m._ssc[0, 0] * (psi ** 2).sum()), r["Std. Error"], rtol=1e-6)
    return {"estimate": r["Estimate"], "se": r["Std. Error"], "psi": psi, "n": m._N}


def pooled(theta, psi, w):
    """Weighted average of hourly estimates. psi holds each hour's influence per OD pair."""
    est = float(np.dot(w, theta))
    # OD pair absent in an hour adds zero
    infl = pd.concat([wh * p for wh, p in zip(w, psi)], axis=1).fillna(0.0).sum(axis=1)
    g = len(infl)
    se = float(np.sqrt(g / (g - 1) * (infl ** 2).sum()))
    return est, se, infl


def difference(infl, a, b):
    # shared OD influences across hours
    d = pd.concat([infl[a], -infl[b]], axis=1).fillna(0.0).sum(axis=1)
    g = len(d)
    return float(np.sqrt(g / (g - 1) * (d ** 2).sum()))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--company", default="all", choices=["all", "uber", "lyft"])
    p.add_argument("--period", default="janmay", choices=list(rh.PERIODS))
    p.add_argument("--hours", default="0-23")
    p.add_argument("--poisson", action="store_true", help="also fit B2 on the grid with zero cells")
    p.add_argument("--out", default="results/reanalysis/b1")
    a = p.parse_args()
    lo, _, hi = a.hours.partition("-")
    hours = range(int(lo), int(hi or lo) + 1)
    con = duckdb.connect()
    con.execute("SET memory_limit = '3GB'; SET threads = 4; SET temp_directory = 'data/tmp'")
    zones = rh.crz_zones()
    rows, fits, w = [], [], []
    for h in hours:
        t0 = time.time()
        df = rh.frame(con, h, a.company, a.period, zones)
        # weights: 2024 trips in this hour
        w.append(df.loc[pd.to_datetime(df.date).dt.year == 2024, "trips"].sum())
        res = hourly(df)
        n = {k: len(df) for k in res}
        if a.poisson:
            del df
            g = grid(con, h, a.company, a.period, zones)
            res["B2"] = poisson(g)
            n["B2"] = res["B2"]["n"]
            del g
        fits.append(res)
        for name, r in res.items():
            rows.append({"company": a.company, "period": a.period, "spec": name, "hour": h,
                         "estimate": r["estimate"], "se": r["se"], "n": n[name], "trips_2024": w[-1]})
        print(f"{h:2d} " + "  ".join(f"{k} {r['estimate']:.4f} ({r['se']:.4f})" for k, r in res.items())
              + f"  {time.time() - t0:.0f}s", flush=True)
    w = np.array(w, float) / sum(w)
    summ, infl = [], {}
    for name in fits[0]:
        est, se, infl[name] = pooled([f[name]["estimate"] for f in fits], [f[name]["psi"] for f in fits], w)
        summ.append((name, est, se))
    est = dict((k, e) for k, e, _ in summ)
    pairs = [("B1", "A")] + ([("B2", "B1"), ("B2", "A")] if a.poisson else [])
    for x, y in pairs:
        summ.append((f"{x} - {y}", est[x] - est[y], difference(infl, x, y)))
    s = pd.DataFrame(summ, columns=["spec", "estimate", "se"])
    s.insert(0, "period", a.period)
    s.insert(0, "company", a.company)
    s["lo"], s["hi"] = s.estimate - 1.96 * s.se, s.estimate + 1.96 * s.se
    if a.poisson:
        # B2: report exp(theta) - 1
        b2 = s.spec == "B2"
        for c in ("estimate", "lo", "hi"):
            s.loc[b2, f"pct_{c}"] = 100 * np.expm1(s.loc[b2, c])
    print(s.round(4).to_string(index=False))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    for frame_, suffix in [(pd.DataFrame(rows), "_hourly.csv"), (s, "_summary.csv")]:
        f = out.with_name(out.name + suffix)
        frame_.to_csv(f, mode="a", header=not f.exists(), index=False)


if __name__ == "__main__":
    main()
