"""Builds notebooks/03_scoring.ipynb (Part C). Execute with papermill after the TSE result exists.

Parameter SIMULATE (float or None): a made-up two-party share for a smoke run. A smoke run writes
nothing to results/scores.csv and labels every output as simulated.
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
nb = nbf.v4.new_notebook()
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
params = code("SIMULATE = None   # papermill parameter: a fake Flávio two-party share for smoke runs only")
params.metadata["tags"] = ["parameters"]

nb.cells = [
md("""# Scoring the forecast against the official result

**Part C of 3.** The forecast in `prereg/forecast_frozen.json` was hashed and timestamped before the polls closed (OpenTimestamps proof: `prereg/BUNDLE.sha256.ots`). This notebook fetches the official TSE count, applies the scoring rules exactly as written in `EXPERIMENT.md`, and appends the scores to `results/scores.csv`. Nothing in Part A is edited.

It also runs the same frozen model, unchanged, on the 2018 and 2022 runoffs, using only the information that was available before each of those elections."""),
params,
code("""import sys, json, hashlib, datetime as dt
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT / "src"))
import numpy as np, pandas as pd, matplotlib, matplotlib.pyplot as plt
import forecast as F, backtest as BT, tse
matplotlib.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False})
FIG = ROOT / "results" / "figures"
frozen = json.loads((ROOT / "prereg" / "forecast_frozen.json").read_text())
bundle_ok = hashlib.sha256((ROOT / "prereg" / "BUNDLE.sha256").read_bytes()).hexdigest()
print("bundle digest:", bundle_ok)
for line in (ROOT / "prereg" / "BUNDLE.sha256").read_text().splitlines():   # the frozen files are untouched
    digest, name = line.split()
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, f"{name} changed after the freeze"
print("all frozen files match their pre-registered hashes")"""),
md("""## 1. The official result"""),
code("""if SIMULATE is None:
    nat = tse.summary(tse.fetch(tse.RUNOFF, "br"))
    status = "final" if (nat["final"] and nat["pct_sections"] >= 100) else f"provisional ({nat['pct_sections']:.2f}% of sections)"
else:
    nat = {"flavio_two_party": float(SIMULATE), "pct_sections": 100.0, "final": True}
    status = "SIMULATED (smoke run, not a result)"
actual = nat["flavio_two_party"]; o = int(actual > 50)
print(f"status: {status}"); print(json.dumps(nat, indent=1, default=float))
print(f"Flávio two-party share = {actual:.3f}%  ->  outcome o = {o}")"""),
md("""## 2. Scores for every arm

Each arm's predictive draws are regenerated from its ledger config, and each is asserted to reproduce the ledger's probability exactly. That way the scores refer to the very distributions that were frozen.

- **Brier score** and **log score** for the binary outcome.
- **Absolute error** of the median.
- **PIT**: the predictive CDF evaluated at the actual share. Across many forecasts this should be uniform. For one forecast, it says where in the distribution reality landed.
- **Coverage** of the 80% and 95% intervals."""),
code("""led = pd.read_csv(F.RESULTS / "ledger.csv", keep_default_na=False)
fields = set(F.ArmConfig.__dataclass_fields__)
def to_cfg(r):
    # Rebuild the exact ArmConfig of a ledger row; the recorded config_hash decides int vs float.
    import itertools
    kw = {k: r[k] for k in fields if k in r}
    for k in ("draws", "tune", "chains", "seed"): kw[k] = int(kw[k])
    kw["drop_low_audit"] = str(kw["drop_low_audit"]) == "True"
    kw["window_from"] = kw["window_from"] or None
    num = ("nu", "err_scale", "deff")
    options = [[float(kw[k])] + ([int(float(kw[k]))] if float(kw[k]).is_integer() else []) for k in num]
    for combo in itertools.product(*options):
        cfg = F.ArmConfig(**{**kw, **dict(zip(num, combo))})
        if cfg.key() == r["config_hash"]:
            return cfg
    raise AssertionError(f"{r['arm']}: no config reproduces ledger hash {r['config_hash']}")
def score(p, v, name, kind):
    pit = float((v < actual).mean()) if v is not None else np.nan
    q = np.percentile(v, [2.5, 10, 50, 90, 97.5]) if v is not None else [np.nan] * 5
    return {"arm": name, "kind": kind, "p_flavio": p, "brier": (p - o) ** 2,
            "log_score": np.log(p if o else 1 - p), "median": q[2], "abs_err_median": abs(q[2] - actual),
            "pit": pit, "in80": bool(q[1] <= actual <= q[3]), "in95": bool(q[0] <= actual <= q[4])}
rows = []
for _, r in led.iterrows():
    cfg = to_cfg(r)
    rr, v = F.run_arm(cfg, write=False)
    assert abs(rr["p_flavio"] - float(r["p_flavio"])) < 1e-9, f"{cfg.arm}: draws do not reproduce the ledger"
    rows.append(score(float(r["p_flavio"]), v, cfg.arm, r["run_class"]))
mkt = frozen["market_comparator_p_flavio"]
rows += [score(0.5, None, "coin flip", "baseline"), score(mkt, None, "prediction markets (de-vigged)", "comparator")]
scores = pd.DataFrame(rows)
scores.round(4)"""),
md("""## 3. The pre-registered verdict

The acceptance rule was fixed in advance. The forecast is "useful" if its Brier score beats a coin (< 0.25) **and** the actual share falls inside its 80% interval."""),
code("""m2 = scores.set_index("arm").loc["M2_bayes_dynamic_hist"]
useful = (m2.brier < 0.25) and m2.in80
verdict = {"status": status, "actual_flavio_two_party": round(actual, 3), "outcome_flavio_won": o,
           "forecast_p_flavio": frozen["p_flavio"], "forecast_median": frozen["median_flavio_vv"],
           "brier": round(m2.brier, 4), "log_score": round(m2.log_score, 4), "abs_err_median_pp": round(m2.abs_err_median, 3),
           "pit": round(m2.pit, 3), "in80": bool(m2.in80), "in95": bool(m2.in95),
           "beats_coin": bool(m2.brier < 0.25), "beats_market": bool(m2.brier < (mkt - o) ** 2),
           "useful_per_preregistration": bool(useful),
           "best_arm_by_abs_err": scores[scores.kind != "baseline"].dropna(subset=["median"]).sort_values("abs_err_median").iloc[0]["arm"]}
print(json.dumps(verdict, indent=1))"""),
code("""v = F.run_arm(F.ArmConfig("M2_bayes_dynamic_hist", run_class="primary", note="headline forecast"), write=False)[1]
fig, ax = plt.subplots(figsize=(8, 3.6))
ax.hist(v, bins=120, density=True, alpha=0.6, label="frozen forecast (M2)")
ax.axvline(actual, c="crimson", lw=2, label=f"official result {actual:.2f}%" + ("" if SIMULATE is None else " (SIMULATED)"))
ax.axvline(50, c="k", lw=0.8); ax.set_xlabel("Flávio, two-party valid votes (%)"); ax.legend(frameon=False, fontsize=8)
ax.set_title(f"Where reality landed: PIT = {m2.pit:.2f}")
fig.tight_layout(); fig.savefig(FIG / ("scored.png" if SIMULATE is None else "scored_SIMULATED.png")); plt.show()"""),
md("""## 4. Backtest: the same frozen model on 2018 and 2022

The model code is imported, not copied (`src/backtest.py` swaps only the data inputs). Each year sees only the Datafolha errors from *earlier* runoffs: 2018 uses 2002-2014 and 2022 uses 2002-2018. The measure is the non-PT finalist's two-party share. Two elections are a small test, so read this as a sanity check, not as a calibration estimate."""),
code("""bt = []
for year in (2018, 2022):
    act = BT.ELECTIONS[year][2]; oo = int(act > 50)
    for cfg in (F.ArmConfig("M2_bayes_dynamic_hist", run_class="primary", note="headline forecast"),
                F.ArmConfig("M3_bayes_dynamic_nobias", bias="none"), F.ArmConfig("M0_naive_last", note="baseline")):
        r, vv = BT.run(year, cfg)
        bt.append({"year": year, "arm": cfg.arm, "n_polls": r["n_polls"], "p_nonpt": r["p_flavio"], "median": r["median"],
                   "actual": act, "abs_err": abs(r["median"] - act), "brier": (r["p_flavio"] - oo) ** 2,
                   "pit": float((vv < act).mean()), "in80": r["pi80_low"] <= act <= r["pi80_high"]})
backtest = pd.DataFrame(bt); backtest.round(3)"""),
md("""## 5. Where the map moved: first round to runoff, state by state

This section is descriptive: the runoff's two-party share in each state against the first round's. It tests one claim from Part B, the regional cleavage measured in the final poll crosstabs (South minus Nordeste: 32 points)."""),
code("""REGION = {**{u: "Nordeste" for u in "al ba ce ma pb pe pi rn se".split()}, **{u: "Sul" for u in "pr rs sc".split()},
          **{u: "Sudeste" for u in "es mg rj sp".split()}, **{u: "Norte" for u in "ac am ap pa ro rr to".split()},
          **{u: "Centro-Oeste" for u in "df go ms mt".split()}, "zz": "Abroad"}
if SIMULATE is None:
    st = []
    for uf in tse.UFS:
        a, b = tse.summary(tse.fetch(tse.RUNOFF, uf)), tse.summary(tse.fetch(tse.FIRST, uf))
        st.append({"uf": uf, "region": REGION[uf], "r2_flavio": a["flavio_two_party"], "r1_flavio": b["flavio_two_party"],
                   "r2_votes": a["flavio_votes"] + a["lula_votes"], "pct_sections": a["pct_sections"]})
    st = pd.DataFrame(st); st["swing"] = st.r2_flavio - st.r1_flavio
    reg = st[st.uf != "zz"].assign(f=lambda d: d.r2_flavio / 100 * d.r2_votes).groupby("region")[["f", "r2_votes"]].sum()
    reg["flavio_two_party"] = 100 * reg.f / reg.r2_votes
    gap = reg.loc["Sul", "flavio_two_party"] - reg.loc["Nordeste", "flavio_two_party"]
    print(f"official South minus Nordeste gap: {gap:.1f} points (Datafolha crosstab: 32)")
    print(f"sum of states vs national (two-party): {100*(st.r2_flavio/100*st.r2_votes).sum()/st.r2_votes.sum():.3f} vs {actual:.3f}")
    display(reg[["flavio_two_party"]].round(2)); display(st.sort_values("swing").round(2))
else:
    print("SIMULATED run: state section skipped")"""),
code("""out = {"verdict": verdict, "scored_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
       "harness_commit": F.harness_commit(), "bundle_digest": bundle_ok}
if SIMULATE is None:
    s = scores.assign(scored_at_utc=out["scored_at_utc"], result_status=status, actual=actual, harness_commit=out["harness_commit"])
    path = F.RESULTS / "scores.csv"; s.to_csv(path, mode="a", header=not path.exists(), index=False)
    (F.RESULTS / "verdict.json").write_text(json.dumps(out, indent=2, default=float))
    backtest.to_csv(F.RESULTS / "backtest.csv", index=False)
print(json.dumps(out, indent=1, default=float))"""),
]
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out = ROOT / "notebooks" / "03_scoring.ipynb"
nbf.write(nb, out)
print(out)
