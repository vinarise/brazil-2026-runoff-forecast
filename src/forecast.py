"""Forecast harness for the 2026 Brazilian presidential runoff.

Every arm is one call to run_arm(); every call appends one row to results/ledger.csv.
Design and constants are pre-registered in EXPERIMENT.md; this file implements them.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RESULTS = ROOT / "results"
LEDGER = RESULTS / "ledger.csv"

DAY0 = pd.Timestamp("2026-10-04")
ELECTION = pd.Timestamp("2026-10-25")
T_ELECTION = (ELECTION - DAY0).days  # 21
SEED = 20261025
VALID_FRACTION = 0.9
N_CAP = 5000
LOW_AUDIT = ("Phoenix", "Vetor/Arrow", "Data Ranking")

# Structural-model constants (M1). Small candidates without published transfer data get
# an ideological prior; the four candidates with survey data use the pooled surveys.
DIRICHLET_KAPPA = 30.0
SMALL_CANDIDATE_PRIOR = {  # (to_flavio, to_lula, rest)
    "flavio": (0.60, 0.20, 0.20),
    "lula": (0.10, 0.70, 0.20),
    "null_vote": (0.05, 0.15, 0.80),
}
SWITCH_SD = 0.015    # half-normal scale of finalists' voters switching sides
TURNOUT_SD = 0.02    # sd of each finalist's relative turnout change


@dataclass(frozen=True)
class ArmConfig:
    arm: str
    run_class: str = "arm"          # primary | arm | sensitivity
    bias: str = "hist"              # hist | none | hist_r1 | lv
    err_model: str = "predictive_t"  # predictive_t (Deviation 1) | as_registered
    houses: str = "all"             # all | established (exploratory, Deviation 2)
    nu: float = 5.0                 # tails of the election-day error
    err_scale: float = 1.0          # multiplier on the historical error SD
    deff: float = 2.0
    window_from: str | None = None  # field midpoint lower bound, ISO date
    drop_low_audit: bool = False
    draws: int = 2000
    tune: int = 2000
    chains: int = 4
    seed: int = SEED
    note: str = ""

    def key(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:16]

    def fit_key(self) -> tuple:
        """Settings that change the poll-model posterior (others act only on election day)."""
        return (self.deff, self.window_from, self.drop_low_audit, self.houses,
                self.draws, self.tune, self.chains, self.seed)


# ---------------------------------------------------------------- data

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_hash() -> str:
    return sha256(ROOT / "prereg" / "data_manifest.sha256")


def verify_manifest() -> None:
    """Fail loudly if any raw file differs from the pre-registered snapshot."""
    for line in (ROOT / "prereg" / "data_manifest.sha256").read_text().splitlines():
        digest, name = line.split()
        actual = sha256(RAW / name)
        if actual != digest:
            raise RuntimeError(f"{name} changed since pre-registration: {actual} != {digest}")


def harness_commit() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "sha256:" + sha256(Path(__file__))


def load_polls(cfg: ArmConfig | None = None) -> pd.DataFrame:
    df = pd.read_csv(RAW / "polls_2026_r2.csv", parse_dates=["published", "field_start", "field_end"])
    df = df[df["include"] == 1].copy()
    df["mid"] = df["field_start"] + (df["field_end"] - df["field_start"]) / 2
    df["t"] = ((df["mid"] - DAY0).dt.total_seconds() / 86400).round().astype(int).clip(0, T_ELECTION)
    df["y"] = 100 * df["flavio_vv"] / (df["flavio_vv"] + df["lula_vv"])
    if cfg is not None:
        if cfg.drop_low_audit:
            df = df[~df["pollster"].isin(LOW_AUDIT)]
        if cfg.window_from:
            df = df[df["mid"] >= pd.Timestamp(cfg.window_from)]
        deff = cfg.deff
    else:
        deff = 2.0
    n_eff = np.minimum(df["n"], N_CAP) * VALID_FRACTION / deff
    p = df["y"] / 100
    df["se"] = 100 * np.sqrt(p * (1 - p) / n_eff)
    return df.sort_values(["mid", "pollster"]).reset_index(drop=True)


def hist_errors(include_r1_2026: bool = False) -> np.ndarray:
    """Non-PT finalist's share, eve-of-runoff poll minus result (pp). Negative = poll understated non-PT."""
    h = pd.read_csv(RAW / "hist_datafolha_runoffs.csv")
    err = (h["result_pt_vv"] - h["poll_pt_vv"]).to_numpy(dtype=float)
    if include_r1_2026:
        err = np.append(err, r1_2026_two_party_errors().mean())
    return err


def r1_2026_two_party_errors() -> np.ndarray:
    """Flávio two-party share in each pollster's final 1st-round poll minus the result (pp)."""
    p = pd.read_csv(RAW / "r1_2026_final_polls.csv")
    r = pd.read_csv(RAW / "r1_2026_result.csv").set_index("candidate")["votes"]
    actual = 100 * r["Flavio Bolsonaro"] / (r["Flavio Bolsonaro"] + r["Lula"])
    poll = 100 * p["flavio_vv"] / (p["flavio_vv"] + p["lula_vv"])
    return (poll - actual).to_numpy(dtype=float)


def market_comparator() -> float:
    m = pd.read_csv(RAW / "markets_2026.csv")
    last = m.sort_values("observed_at_brt").groupby("venue").tail(1)
    return float((last["flavio_price"] / (last["flavio_price"] + last["lula_price"])).mean())


# ---------------------------------------------------------------- poll model

_FIT_CACHE: dict[tuple, dict] = {}


def fit_poll_model(cfg: ArmConfig) -> dict:
    """Dynamic Bayesian aggregation with house effects. Cached per fit_key."""
    if cfg.fit_key() in _FIT_CACHE:
        return _FIT_CACHE[cfg.fit_key()]
    import arviz as az
    import pymc as pm

    df = load_polls(cfg)
    houses = sorted(df["pollster"].unique())
    hidx = df["pollster"].map({h: i for i, h in enumerate(houses)}).to_numpy()
    with pm.Model() as model:
        mu0 = pm.Normal("mu0", 50.0, 3.0)
        tau = pm.HalfNormal("tau", 0.25)
        z = pm.Normal("z", 0.0, 1.0, shape=T_ELECTION)
        mu = pm.Deterministic("mu", pm.math.concatenate([[mu0], mu0 + pm.math.cumsum(tau * z)]))
        sigma_h = pm.HalfNormal("sigma_h", 1.5)
        h_raw = pm.Normal("h_raw", 0.0, 1.0, shape=len(houses))
        if cfg.houses == "established":
            # Reference = houses with a scorable 2026 first-round final poll (Deviation 2).
            ref = set(pd.read_csv(RAW / "r1_2026_final_polls.csv")["pollster"])
            ref_idx = np.array([i for i, h_ in enumerate(houses) if h_ in ref])
            h = pm.Deterministic("house", sigma_h * (h_raw - h_raw[ref_idx].mean()))
        else:
            h = pm.Deterministic("house", sigma_h * (h_raw - h_raw.mean()))
        sigma_x = pm.HalfNormal("sigma_x", 1.0)
        scale = pm.math.sqrt(df["se"].to_numpy() ** 2 + sigma_x**2)
        pm.StudentT("y", nu=7, mu=mu[df["t"].to_numpy()] + h[hidx], sigma=scale, observed=df["y"].to_numpy())
        idata = pm.sample(draws=cfg.draws, tune=cfg.tune, chains=cfg.chains, random_seed=cfg.seed,
                          target_accept=0.95, progressbar=False)
        pm.sample_posterior_predictive(idata, extend_inferencedata=True, random_seed=cfg.seed, progressbar=False)
    summ = az.summary(idata, var_names=["mu", "tau", "sigma_h", "sigma_x", "house"], round_to=4)
    mu_T = idata.posterior["mu"].sel(mu_dim_0=T_ELECTION).values.reshape(-1)
    out = {
        "idata": idata, "df": df, "houses": houses, "summary": summ, "mu_T": mu_T,
        "rhat_max": float(summ["r_hat"].max()),
        "ess_mu_T": float(summ.loc[f"mu[{T_ELECTION}]", "ess_bulk"]),
        "rhat_mu_T": float(summ.loc[f"mu[{T_ELECTION}]", "r_hat"]),
    }
    _FIT_CACHE[cfg.fit_key()] = out
    return out


def election_day(mu_T: np.ndarray, cfg: ArmConfig, rng: np.random.Generator) -> np.ndarray:
    """V = mu_T + election-day error, under the arm's error assumptions."""
    if cfg.err_model == "predictive_t":
        return mu_T + predictive_t_error(cfg, rng, mu_T.size)
    if cfg.err_model != "as_registered":
        raise ValueError(f"unknown err_model {cfg.err_model!r}")
    base = hist_errors(include_r1_2026=False)
    e_sd = base.std(ddof=1) * cfg.err_scale
    if cfg.bias == "hist":
        err = base
        b = rng.normal(-err.mean(), err.std(ddof=1) / np.sqrt(len(err)), mu_T.size)
    elif cfg.bias == "hist_r1":
        err = hist_errors(include_r1_2026=True)
        b = rng.normal(-err.mean(), err.std(ddof=1) / np.sqrt(len(err)), mu_T.size)
    elif cfg.bias == "lv":
        lv = pd.read_csv(RAW / "likely_voter_2026.csv")
        delta = (lv["flavio_vv"] - lv["overall_flavio_vv"]).to_numpy(dtype=float)
        b = rng.normal(delta.mean(), delta.std(ddof=1) / np.sqrt(len(delta)), mu_T.size)
    elif cfg.bias == "none":
        b = np.zeros(mu_T.size)
    else:
        raise ValueError(f"unknown bias {cfg.bias!r}")
    t_scale = e_sd / np.sqrt(cfg.nu / (cfg.nu - 2)) if cfg.nu > 2 else e_sd
    e = stats.t.rvs(cfg.nu, scale=t_scale, size=mu_T.size, random_state=rng)
    return mu_T + b + e


def predictive_t_error(cfg: ArmConfig, rng: np.random.Generator, size: int) -> np.ndarray:
    """Posterior predictive of next year's error given n past errors (normal model, flat prior):
    a Student t centred on the mean error with scale s*sqrt(1 + 1/n). Deviation 1 in EXPERIMENT.md."""
    err = hist_errors(include_r1_2026=(cfg.bias == "hist_r1"))
    n, s = len(err), err.std(ddof=1) * cfg.err_scale
    scale2 = s**2 * (1 + 1 / n)
    if cfg.bias in ("hist", "hist_r1"):
        loc = -err.mean()
    elif cfg.bias == "none":
        loc = 0.0
    elif cfg.bias == "lv":
        lv = pd.read_csv(RAW / "likely_voter_2026.csv")
        delta = (lv["flavio_vv"] - lv["overall_flavio_vv"]).to_numpy(dtype=float)
        loc, scale2 = delta.mean(), scale2 + delta.var(ddof=1) / len(delta)
    else:
        raise ValueError(f"unknown bias {cfg.bias!r}")
    return loc + stats.t.rvs(cfg.nu, scale=np.sqrt(scale2), size=size, random_state=rng)


# ---------------------------------------------------------------- non-Bayesian arms

def naive_last(cfg: ArmConfig, rng: np.random.Generator, n: int = 200_000) -> np.ndarray:
    df = load_polls(cfg)
    last = df[df["published"] >= "2026-10-18"].sort_values("published").groupby("pollster").tail(1)
    sd = 1.81 * cfg.err_scale
    return last["y"].mean() + stats.t.rvs(cfg.nu, scale=sd / np.sqrt(cfg.nu / (cfg.nu - 2)), size=n, random_state=rng)


def structural(cfg: ArmConfig, rng: np.random.Generator, n: int = 200_000) -> np.ndarray:
    r1 = pd.read_csv(RAW / "r1_2026_result.csv")
    tr = pd.read_csv(RAW / "transfers_2026.csv")
    F = float(r1.loc[r1.candidate == "Flavio Bolsonaro", "votes"].iloc[0])
    L = float(r1.loc[r1.candidate == "Lula", "votes"].iloc[0])
    sF = np.abs(rng.normal(0, SWITCH_SD, n)); sL = np.abs(rng.normal(0, SWITCH_SD, n))
    f = F * (1 - sF) + L * sL
    l = L * (1 - sL) + F * sF
    f *= 1 + rng.normal(0, TURNOUT_SD, n); l *= 1 + rng.normal(0, TURNOUT_SD, n)
    for _, c in r1[~r1.endorsed_in_r2.eq("finalist")].iterrows():
        rows = tr[tr.r1_candidate == c.candidate]
        if len(rows):
            tf = rows["to_flavio"].mean() / 100
            tl = rows["to_lula"].dropna().mean() / 100 if rows["to_lula"].notna().any() else (1 - tf) / 2
            alpha = np.array([tf, tl, max(1 - tf - tl, 0.02)])
        else:
            alpha = np.array(SMALL_CANDIDATE_PRIOR.get(c.endorsed_in_r2, (1 / 3, 1 / 3, 1 / 3)))
        w = rng.dirichlet(DIRICHLET_KAPPA * alpha / alpha.sum(), n)
        f += c.votes * w[:, 0]; l += c.votes * w[:, 1]
    return 100 * f / (f + l)


# ---------------------------------------------------------------- diagnostics

def herding_test(cfg: ArmConfig | None = None, since: str = "2026-10-20") -> dict:
    """Do the final polls agree more than their sample sizes allow? (lower-tail chi-square)"""
    df = load_polls(cfg or ArmConfig("herding", deff=1.0))
    last = df[df["field_end"] >= since].sort_values("published").groupby("pollster").tail(1)
    w = 1 / last["se"] ** 2
    ybar = float((w * last["y"]).sum() / w.sum())
    chi2 = float((((last["y"] - ybar) / last["se"]) ** 2).sum())
    k = len(last)
    return {"k": k, "weighted_mean": ybar, "chi2": chi2, "dof": k - 1,
            "ratio": chi2 / (k - 1), "p_lower": float(stats.chi2.cdf(chi2, k - 1)),
            "p_upper": float(stats.chi2.sf(chi2, k - 1))}


# ---------------------------------------------------------------- arms + ledger

def summarize(v: np.ndarray) -> dict:
    p = float((v > 50).mean())
    mcse = float(np.sqrt(p * (1 - p) / v.size))
    q = np.percentile(v, [2.5, 10, 50, 90, 97.5])
    return {"p_flavio": round(p, 4), "p_mcse": round(mcse, 4), "median": round(q[2], 3),
            "pi80_low": round(q[1], 3), "pi80_high": round(q[3], 3),
            "pi95_low": round(q[0], 3), "pi95_high": round(q[4], 3), "n_draws": int(v.size)}


def run_arm(cfg: ArmConfig, write: bool = True) -> tuple[dict, np.ndarray]:
    rng = np.random.default_rng([cfg.seed, int(cfg.key(), 16) % (2**32)])
    n_polls = 0 if cfg.arm.startswith("M1") else len(load_polls(cfg))  # M1 uses no runoff polls
    diag = {"rhat_max": "", "rhat_mu_T": "", "ess_mu_T": "", "n_polls": n_polls}
    if cfg.arm.startswith("M0"):
        v = naive_last(cfg, rng)
    elif cfg.arm.startswith("M1"):
        v = structural(cfg, rng)
    else:
        fit = fit_poll_model(cfg)
        v = election_day(fit["mu_T"], cfg, rng)
        diag.update(rhat_max=round(fit["rhat_max"], 4), rhat_mu_T=round(fit["rhat_mu_T"], 4),
                    ess_mu_T=round(fit["ess_mu_T"], 1))
    status = "ok"
    if diag["rhat_mu_T"] != "" and (diag["rhat_mu_T"] >= 1.01 or diag["ess_mu_T"] <= 1000):
        status = "failed_convergence"
    row = {"run_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "arm": cfg.arm, "run_class": cfg.run_class, "config_hash": cfg.key(),
           "data_manifest_sha256": manifest_hash(), "harness_commit": harness_commit(),
           **{k: v_ for k, v_ in asdict(cfg).items() if k not in ("arm", "run_class")},
           **diag, **summarize(v), "status": status, "supersedes": ""}
    if write:
        RESULTS.mkdir(exist_ok=True)
        header = not LEDGER.exists()
        pd.DataFrame([row]).to_csv(LEDGER, mode="a", header=header, index=False)
    return row, v
