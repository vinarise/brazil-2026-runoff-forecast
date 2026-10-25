"""Runs the frozen M2 model, unchanged, on the 2018 and 2022 runoffs.

The model code is not copied: forecast.py is imported and only its data inputs are swapped, so
the backtest exercises exactly the code that produced the 2026 forecast. The error history is
time-respecting: each year sees only the Datafolha errors of earlier runoffs.
"""
from __future__ import annotations

import contextlib

import numpy as np
import pandas as pd

import forecast as F

BT = F.ROOT / "data" / "backtest"
ELECTIONS = {  # year: (first-round date, runoff date, official non-PT two-party share)
    2018: ("2018-10-07", "2018-10-28", 55.13),
    2022: ("2022-10-02", "2022-10-30", 49.10),
}


def load(year: int, deff: float = 2.0) -> pd.DataFrame:
    day0, election, _ = ELECTIONS[year]
    df = pd.read_csv(BT / f"polls_{year}_r2.csv", parse_dates=["published", "field_start", "field_end"])
    df = df.dropna(subset=["pt_vv", "nonpt_vv", "n", "field_start", "field_end"]).copy()
    T = (pd.Timestamp(election) - pd.Timestamp(day0)).days
    df["mid"] = df["field_start"] + (df["field_end"] - df["field_start"]) / 2
    df["t"] = ((df["mid"] - pd.Timestamp(day0)).dt.total_seconds() / 86400).round().astype(int).clip(0, T)
    df["y"] = 100 * df["nonpt_vv"] / (df["nonpt_vv"] + df["pt_vv"])
    p = df["y"] / 100
    df["se"] = 100 * np.sqrt(p * (1 - p) / (np.minimum(df["n"], F.N_CAP) * F.VALID_FRACTION / deff))
    return df.sort_values(["mid", "pollster"]).reset_index(drop=True)


def past_errors(year: int) -> np.ndarray:
    h = pd.read_csv(F.RAW / "hist_datafolha_runoffs.csv")
    h = h[h["year"] < year]
    return (h["result_pt_vv"] - h["poll_pt_vv"]).to_numpy(dtype=float)


@contextlib.contextmanager
def swapped_inputs(year: int):
    day0, election, _ = ELECTIONS[year]
    saved = (F.load_polls, F.T_ELECTION, F.DAY0, F.ELECTION, F.hist_errors)
    F.load_polls = lambda cfg=None: load(year, cfg.deff if cfg else 2.0)
    F.T_ELECTION = (pd.Timestamp(election) - pd.Timestamp(day0)).days
    F.DAY0, F.ELECTION = pd.Timestamp(day0), pd.Timestamp(election)
    F.hist_errors = lambda include_r1_2026=False: past_errors(year)
    F._FIT_CACHE.clear()
    try:
        yield
    finally:
        F.load_polls, F.T_ELECTION, F.DAY0, F.ELECTION, F.hist_errors = saved
        F._FIT_CACHE.clear()


def naive_last(year: int, cfg: F.ArmConfig, rng: np.random.Generator, n: int = 200_000) -> np.ndarray:
    """M0 with the same rule as 2026: each pollster's last poll published in the final week."""
    _, election, _ = ELECTIONS[year]
    df = load(year)
    last = df[df["published"] >= pd.Timestamp(election) - pd.Timedelta(days=7)]
    last = last.sort_values("published").groupby("pollster").tail(1)
    sd = 1.81 * cfg.err_scale
    from scipy import stats
    return last["y"].mean() + stats.t.rvs(cfg.nu, scale=sd / np.sqrt(cfg.nu / (cfg.nu - 2)), size=n, random_state=rng)


def run(year: int, cfg: F.ArmConfig) -> tuple[dict, np.ndarray]:
    saved_naive = F.naive_last
    F.naive_last = lambda cfg_, rng, n=200_000: naive_last(year, cfg_, rng, n)
    try:
        with swapped_inputs(year):
            row, v = F.run_arm(cfg, write=False)
    finally:
        F.naive_last = saved_naive
    row["year"], row["actual"] = year, ELECTIONS[year][2]
    return row, v
