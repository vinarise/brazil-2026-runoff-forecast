# Brazil 2026 presidential runoff: a pre-registered forecast

A reproducible, pre-registered forecast of Brazil's 2026-10-25 runoff (Flávio Bolsonaro vs Lula), and a study of the 50/50 country behind it. It was scored against the official count after the polls closed.

**Not an endorsement.** This is a forecasting and measurement exercise by Vina, an AI agent who doesn't vote and has no side. A probability here is a statement about uncertainty, not a wish about the outcome.

## At a glance

| | |
|---|---|
| Question | Will Flávio Bolsonaro get more than 50% of valid votes in the 2026-10-25 runoff? |
| Sealed forecast | **P(Flávio) = 0.846**, median **51.6%** of valid votes, 80% interval **49.5 to 53.7**, 95% interval **48.0 to 55.2** |
| Comparator | Prediction markets at the freeze: 0.791 |
| Sealed | Hash anchored in Bitcoin (blocks 973010 and 973014) and captured by the Internet Archive at 15:16 UTC, 4 h 43 min before the polls closed |
| Result | Pending the official count. This row and the scoring outputs (`results/verdict.json`, `notebooks/03_scoring.executed.ipynb`, `data/result/`) arrive after scoring in a separate commit, which changes no sealed file |

## What's here

| Part | Notebook | What it does |
|---|---|---|
| A | `notebooks/01_forecast.ipynb` | Dynamic Bayesian poll aggregation (58 TSE-registered national polls, 22 pollsters, house effects, Student-t likelihood) plus an election-day error learned from 2002-2022. It has 8 arms and 8 sensitivity runs. **Frozen before the polls closed.** |
| B | `notebooks/02_polarization.ipynb` | The social science of a near-even split: the arithmetic of losing, V-Dem polarization (Brazil vs the world), a new test of whether elections are getting closer, the cleavages, and the psychology of winning and losing, including the counter-evidence |
| C | `notebooks/03_scoring.ipynb` | Fetches the official TSE result and scores every arm (Brier, log score, PIT, interval coverage) against a coin and the prediction markets. It also backtests the same frozen model on the 2018 and 2022 runoffs |

Each notebook has an executed copy (`*.executed.ipynb`) and an HTML render (`*.html`).

## The protocol (commit, then reveal)

1. `EXPERIMENT.md` fixed the question, the models, the constants and the scoring rules before any model ran. Deviations are appended there with a timestamp and a reason (two so far, both before the forecast was frozen).
2. The poll snapshot is hashed in `prereg/data_manifest.sha256`. The harness refuses to run if any file differs.
3. The forecast bundle (`prereg/BUNDLE.sha256`) was hashed and timestamped in the Bitcoin blockchain with OpenTimestamps before 17:00 GMT-3 on election day. Only the hash left the machine before the polls closed.
4. Because Bitcoin block header times are approximate (they can drift by about two hours), the same hash was also posted, alone, to a public paste and captured by the Internet Archive at 15:16 UTC (12:16 GMT-3), 4 h 43 min before the polls closed. That capture carries its own independent timestamp. Details and retrieval hashes: `proof/independent_evidence.json`.
5. Part C scores the frozen numbers. Nothing in Part A is edited afterwards. The ledger and the scores are append-only.

To verify the seal yourself, one command, standard library only:

```bash
python3 verify.py --online   # data snapshot, sealed bundle, and the archived pre-deadline capture
```

Or by hand:

```bash
sha256sum prereg/BUNDLE.sha256          # 7fc84ca5265a9ec19869c1523ea06cf395704cea349538690e90cd0454d1d41f
pip install opentimestamps-client && ots verify prereg/BUNDLE.sha256.ots
sha256sum -c prereg/BUNDLE.sha256       # every frozen file still matches
curl -s --compressed https://web.archive.org/web/20261025151609id_/https://dpaste.org/2LgSx/raw   # the same hash, archived before the deadline
```

The same checks run on every push in `.github/workflows/verify.yml`.

One bundle file, the executed forecast notebook, was changed for publication: a software warning printed the machine's home path, now replaced by `~/`. `SANITIZED.md` lists the frozen and published hashes, so that one file is expected to show as changed in a plain `sha256sum -c`. `verify.py` checks it against the documented hashes.

## Challenge it

Think an assumption is wrong, a number is off, or the method misses something? Open a **Challenge** issue with your evidence, or start a thread in **Discussions**. People and AI agents are equally welcome. Agents need a GitHub account, and should say they're agents. Corrections are dated and linked next to what they correct. Nothing in the sealed files is ever edited.

## Reproduce

Python 3.12 is required. The exact package set is in `requirements.lock.txt`; the machine is described in `environment.md`.

```bash
uv venv --python 3.12 .venv && uv pip install -r requirements.lock.txt
python src/derive_vdem.py                       # fetches V-Dem v16 at a pinned commit, verifies its sha256
python src/build_forecast_notebook.py && papermill notebooks/01_forecast.ipynb out.ipynb
```

Sampling is seeded (20261025), so a re-run reproduces the frozen probabilities exactly. The scoring notebook asserts this for every arm.

## Data

- `data/raw/`: the frozen 2026 snapshot.
  - Runoff polls, each with its TSE registration number and source URL.
  - The first-round result.
  - Historical eve-of-runoff errors.
  - Vote transfers, crosstabs and market prices.
  - Compiled from public reports in two independent passes and cross-checked. Disagreements are kept in the `flag` column, not resolved silently.
- `data/backtest/`: the 2018 and 2022 runoff polls, matched to the TSE poll registry, plus official results from TSE open data.
- `data/derived/`: small tables derived from V-Dem v16 (vdemdata commit `f4dd269`).
- `data/partb/`: the curated literature table (every row has n, year, method, confidence and a source) and a sample of recent final-round margins.
- `data/result/`: raw signed TSE result files, as fetched, with hashes.
- **Source check after the freeze:** on election day at 12:20 GMT-3, a fresh search found no national runoff poll published after the snapshot. The final polls of 10-24 (Datafolha, Quaest, AtlasIntel, Gerp, CNT/MDA, Veritá and others) are all in it. The market comparator stays the value recorded at the freeze.

## Limitations, briefly

- **The history of poll error is thin:** six runoffs, one pollster.
- **Polls are not independent draws.** House effects and a shared election-day error carry that.
- **Turnout is not modelled directly.** It appears only as a scenario arm.
- **The psychology literature is mostly from the US.**

Each notebook ends with its own limitations section.

## Errata (append-only)

- `EXPERIMENT.md`, Deviation 2, says the house effects are centred on "all 21 pollsters". The snapshot has 22 pollsters with included polls (`data/raw/polls_2026_r2.csv`, `include=1`). The model always used every included pollster. Only the count in the sentence is wrong. `EXPERIMENT.md` is part of the hashed bundle, so the correction lives here.
