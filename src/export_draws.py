"""Exports the frozen predictive draws of the eight arms for the vinarise.com assumptions explorer.

Each arm is re-run from its ledger config (the recorded config_hash must match), and its P(>50) and
median must reproduce prereg/forecast_frozen.json to 3 decimals, or the export aborts. Summaries
(p_win, median, intervals, quantiles) come from the full draws; draws_x100 is a fixed-seed
subsample of N_SUB draws, rounded to integer share x 100. Writes results/draws_explorer.json.
Nothing here writes to the ledger.
"""
from __future__ import annotations

import itertools
import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import forecast as F  # noqa: E402

SCHEMA = "vinarise.draws/0.1"
N_SUB = 2000
TOL = 5e-4  # "to 3 decimals"
QUANTILES = (0.025, 0.1, 0.25, 0.5, 0.75, 0.9, 0.975)
OUT = F.RESULTS / "draws_explorer.json"

# One line per arm, taken from EXPERIMENT.md (primary section, arm table and Deviations 1 and 2).
LABELS = {
    "M2_bayes_dynamic_hist": "Headline forecast: a dynamic Bayesian average of the runoff polls with house effects, "
                             "plus the historical eve-of-runoff polling error (Datafolha, 2002 to 2022).",
    "M2_as_registered": "M2 with the election-day error in the form first registered, which understates the "
                        "uncertainty of having only six past elections (Deviation 1).",
    "M0_naive_last": "The simplest credible baseline: the mean of each pollster's last poll (published from "
                     "2026-10-18), plus an election-day error with SD 1.81.",
    "M1_structural": "Independent of runoff polls: the first-round result plus transfers of eliminated candidates' "
                     "voters, cross-switching and turnout noise; narrow by construction, so read its median.",
    "M3_bayes_dynamic_nobias": "M2 with no historical bias term (b = 0): how much the history-of-error assumption "
                               "moves the answer.",
    "M4_bayes_dynamic_hist_r1": "M2 with the mean bias also using the 2026 first-round polling error: the "
                                "\"polls missed the right again\" scenario.",
    "M5_bayes_dynamic_lv": "Turnout scenario: M2 shifted by the mean likely-voter delta the pollsters published, "
                           "with b = 0 to avoid counting it twice.",
    "M2_established": "Exploratory: M2 with house effects centred on the 11 pollsters that have a scorable 2026 "
                      "first-round final poll (Deviation 2).",
}


def to_cfg(r: pd.Series) -> F.ArmConfig:
    """Rebuild the exact ArmConfig of a ledger row; the recorded config_hash decides int vs float."""
    kw = {k: r[k] for k in F.ArmConfig.__dataclass_fields__ if k in r}
    for k in ("draws", "tune", "chains", "seed"):
        kw[k] = int(kw[k])
    kw["drop_low_audit"] = str(kw["drop_low_audit"]) == "True"
    kw["window_from"] = kw["window_from"] or None
    num = ("nu", "err_scale", "deff")
    options = [[float(kw[k])] + ([int(float(kw[k]))] if float(kw[k]).is_integer() else []) for k in num]
    for combo in itertools.product(*options):
        cfg = F.ArmConfig(**{**kw, **dict(zip(num, combo))})
        if cfg.key() == r["config_hash"]:
            return cfg
    raise SystemExit(f"{r['arm']}: no config reproduces ledger hash {r['config_hash']}")


def main() -> None:
    F.verify_manifest()
    frozen = json.loads((F.ROOT / "prereg" / "forecast_frozen.json").read_text())
    led = pd.read_csv(F.LEDGER, keep_default_na=False)
    led = led[led["arm"].isin(frozen["arms"])]
    if sorted(led["arm"]) != sorted(frozen["arms"]):
        raise SystemExit(f"ledger arms {sorted(led['arm'])} != frozen arms {sorted(frozen['arms'])}")
    led = led.set_index("arm", drop=False)

    arms, failures = {}, []
    for name, fz in frozen["arms"].items():
        cfg = to_cfg(led.loc[name])
        row, v = F.run_arm(cfg, write=False)
        p, med = float((v > 50).mean()), float(np.percentile(v, 50))
        ok = abs(p - fz["p_flavio"]) < TOL and abs(med - fz["median"]) < TOL and row["status"] == "ok"
        print(f"{name:26s} P frozen {fz['p_flavio']:.4f} recomputed {p:.4f} | "
              f"median frozen {fz['median']:.3f} recomputed {med:.3f} | n={v.size} {'ok' if ok else 'MISMATCH'}",
              flush=True)
        if not ok:
            failures.append(name)
            continue
        idx = np.random.default_rng([F.SEED, zlib.crc32(name.encode())]).choice(v.size, N_SUB, replace=False)
        qv = np.quantile(v, QUANTILES)
        arms[name] = {
            "p_win": row["p_flavio"], "median": row["median"],
            "pi80": [row["pi80_low"], row["pi80_high"]], "pi95": [row["pi95_low"], row["pi95_high"]],
            "q": {str(q): round(float(x), 3) for q, x in zip(QUANTILES, qv)},
            "draws_x100": np.rint(v[idx] * 100).astype(int).tolist(),
        }
    if failures:
        raise SystemExit(f"frozen check failed for {failures}; nothing written")

    out = {"schema": SCHEMA, "unit": "flavio_valid_vote_pct", "n_draws": N_SUB, "seed": F.SEED,
           "harness_commit": F.harness_commit(), "frozen_check": "pass",
           "arms": arms, "labels": {k: LABELS[k] for k in arms},
           "market_p": frozen["market_comparator_p_flavio"]}
    OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False) + "\n")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
