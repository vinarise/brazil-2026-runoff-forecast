# EXPERIMENT: forecasting the 2026 Brazilian presidential runoff

Pre-registration. Written 2026-10-25, about 00:40 GMT-3, before any model in this directory had been run. The election is today. Polls close at 17:00 GMT-3.

Not an endorsement. This is a measurement exercise: how well can a reproducible, published, pre-registered model forecast a near-50/50 national election? The author has no vote and no side.

## Question

What is the probability that Flávio Bolsonaro (PL) gets more than 50% of the valid votes in the runoff of 2026-10-25 against Lula (PT)? What is the predictive distribution of his valid-vote share?

## Hypothesis

The final polls put Flávio near 51% of valid votes. Brazilian eve-of-runoff polls have historically missed the non-PT finalist's share by about one point, with a slight tendency to understate the non-PT candidate. So the hypothesis is a favourite, not a certainty: P(Flávio) between 0.6 and 0.85.

## Primary forecast (pre-registered, the number we are scored on)

Arm **M2 `bayes_dynamic_hist`**:

1. **Data:** every national runoff poll in `data/raw/polls_2026_r2.csv` with `include=1` (TSE-registered). Each poll is dated at its field midpoint; day 0 is 2026-10-04.
2. **Measure:** Flávio's two-party valid-vote share, in percentage points.
3. **Latent support:** a Gaussian random walk μ_t from day 0 to day 21 (election day).
   - Prior: μ_0 ~ N(50, 3).
   - Daily step: τ ~ HalfNormal(0.25).
4. **House effects:** h_j ~ N(0, σ_h) with σ_h ~ HalfNormal(1.5). They are centred to sum to zero, so μ is the average pollster.
5. **Poll likelihood:** y_i ~ StudentT(ν=7, μ_{t_i} + h_{j(i)}, sqrt(se_i² + σ_x²)).
   - Sampling error: se_i = 100·sqrt(p(1−p)/n_eff,i).
   - Effective sample size: n_eff = min(n, 5000) × 0.9 / deff, with deff = 2.
     - The 0.9 is the valid-vote fraction.
     - The 5000 cap stops rolling trackers from dominating.
   - Extra, non-sampling noise: σ_x ~ HalfNormal(1.0). It absorbs rounding and method noise.
6. **Election day:** V = μ_21 + b + e. Both terms come from `data/raw/hist_datafolha_runoffs.csv`, the eve-of-runoff Datafolha poll versus the result, 2002 to 2022, n = 6. Error is defined as the non-PT share, poll minus result.
   - b, the industry-wide bias: b ~ N(−mean(error), sd(error)/sqrt(6)).
   - e, this year's own error: e ~ StudentT(ν=5) scaled so that SD(e) = sd(error).
7. **Inference:** NUTS, 4 chains × 2000 draws after 2000 tuning, random seed 20261025.
   - Required convergence: R-hat < 1.01 and bulk ESS > 1000 for μ_21.
   - If either fails, the run is a failure, not a forecast.
8. **Outputs:**
   - P(V > 50).
   - Median of V, with 80% and 95% predictive intervals.

## Other arms (reported, not scored as the primary)

| Arm | What changes from M2 | Why it is here |
|---|---|---|
| M0 `naive_last` | Mean of each pollster's last poll (published from 2026-10-18), plus e ~ StudentT(5) with SD 1.81 | The simplest credible baseline |
| M1 `structural` | First-round result, plus transfers of eliminated candidates' voters (pooled survey estimates, Dirichlet), plus symmetric cross-switching and turnout noise | Independent of runoff toplines |
| M3 `bayes_dynamic_nobias` | b = 0 | How much the history-of-error assumption moves the answer |
| M4 `bayes_dynamic_hist_r1` | The mean bias also uses the 2026 first-round two-party error (one pooled observation, weight 1) | The "polls missed the right again" scenario |
| M5 `bayes_dynamic_lv` | μ_21 shifted by the mean likely-voter delta the pollsters published, with b = 0 to avoid counting it twice | Turnout scenario |

Sensitivity grid on M2:
- Error tails ν ∈ {3, 5, 30}.
- Error SD × {0.75, 1, 1.5}.
- Design effect deff ∈ {1.5, 2, 3}.
- Low-auditability rows (Phoenix, Vetor/Arrow, Data Ranking) excluded.
- Window limited to polls with field midpoint from 2026-10-15.

Diagnostics:
- **Herding:** observed dispersion of final-week polls against the dispersion implied by their sample sizes. A ratio < 1 suggests herding.
- **Posterior predictive check:** each poll inside its own predictive interval.
- **House effects:** the house-effect table.

External comparator (not a model): de-vigged prediction-market price. This is the mean of the last Polymarket and Kalshi snapshots in `data/raw/markets_2026.csv`, each normalised so that the two prices sum to 1.

## Scoring (fixed now, applied after the TSE result)

Let o = 1 if Flávio's official valid-vote share is above 50%, else 0. Let P be the M2 probability.

- **Brier** = (P − o)². **Log score** = ln(P) if o = 1, else ln(1 − P).
  - Baselines: a coin at 0.5 (Brier 0.25, log −0.693) and the market comparator.
- **Vote share:**
  - Absolute error of the median.
  - PIT (the predictive CDF evaluated at the actual share).
  - Coverage of the 80% and 95% intervals.
- **Same scores for every arm,** so we can see which assumption was right, without re-choosing the primary.
- **Acceptance rule:** the forecast counts as "useful" if its Brier score beats the coin (< 0.25) and the actual share falls inside the 80% interval. Otherwise it is reported as a miss, with the reason.

## Frozen constants

- Python 3.12, pymc 5.23.0, arviz 0.21.0, numpy 2.2.6, pandas 2.2.3, scipy 1.15.3. The exact environment is in `environment.md`.
- Seed 20261025.
- Data snapshot: the SHA-256 of every file in `data/raw/`, written to `prereg/data_manifest.sha256` before the first run.

## Commit, then reveal

1. Hash the bundle: `prereg/forecast_frozen.json`, plus the ledger, plus `data_manifest.sha256`, plus this file.
2. Timestamp the bundle hash before 17:00 GMT-3, using OpenTimestamps (anchored in Bitcoin) and the git commit.
3. Publish only the hash before the polls close. Publish the full content after they close.

## Confound checklist

- [ ] **Provenance:**
  - Poll rows were compiled from public reports by two independent compilations and cross-checked.
  - Rows that disagreed are flagged in the `flag` column.
  - Every row carries its source URL and TSE registration number.
- [ ] **Independence:** polls are not independent draws. House effects absorb pollster lean. Overlapping rolling-tracker releases are capped (n at most 5000 before the valid-vote and design-effect factors) and flagged. Shared industry error sits in b, not in the poll noise.
- [ ] **Rounding:** most published valid-vote shares are rounded to integers. σ_x absorbs this; the variance of rounding alone is about 0.08.
- [ ] **Calculated shares:** valid-vote shares computed from totals (`vv_calc=1`) assume blank, null and undecided split away evenly. They are flagged.
- [ ] **Historical calibration:** the history is one pollster (Datafolha) over 6 elections, and is applied to the average pollster. This is a known approximation. M3 and M4 bracket it.
- [ ] **Turnout:** not modelled directly in M2. M5 is the turnout scenario.
- [ ] **Late events:** the last polls ended between 2026-10-22 and 2026-10-24. Any movement on election day itself is in e.
- [ ] **Market comparator:** markets see the same polls. They are a comparator, not independent evidence.

## Deviations from this pre-registration (append-only)

### Deviation 1: election-day error, written 2026-10-25 01:05 GMT-3, after a smoke run, before any ledger row

**What was registered.** b ~ N(−mean, s/√6), plus e ~ StudentT(5) scaled so that SD(e) = s. Here s is the SD of the six historical errors, s = 1.26.

**The flaw.** Under a normal error model with an unknown mean and variance, the textbook posterior predictive for next year's error, given n = 6 past errors, is a Student t:
- 5 degrees of freedom,
- centre −mean,
- scale s·√(1 + 1/n), so SD ≈ 1.40·s.

The registered form puts s on the SD instead of on the scale. Its spread is about 1.08·s, which understates the uncertainty that comes from having only six past elections.

**How it was found.** In a smoke run (500 draws, ledger not written), M2 as registered gave P(Flávio) = 0.89 with an 80% interval of 49.9–53.2. That looked too narrow for a model calibrated on n = 6.

**The change.** The direction of the change was known when we made it: it lowers P. It is made on statistical grounds, not to reach a target number.
- The amended form is `err_model=predictive_t`, the default for every Bayesian arm.
- The registered form still runs, as arm `M2_as_registered`, and is scored too.
- **The headline forecast is M2 with `predictive_t`.**
- M0, the naive baseline, keeps its registered error (SD 1.81).

### Deviation 2: exploratory house-reference arm, written 2026-10-25 01:05 GMT-3

M2 centres house effects on the average of all 21 pollsters. Several of them have no public track record, and these lean toward Flávio.

The added arm is `M2_established`. It centres house effects on the 11 pollsters with a scorable 2026 first-round final poll (`r1_2026_final_polls.csv`). That is an objective rule, chosen before this arm was run.

This arm is labelled exploratory. It is a sensitivity check, not the headline.

### Smoke-run observations (no ledger rows; recorded for transparency)

- Herding test (last poll per house, field ending from 10-20, k = 19, deff = 1): χ²/dof = 0.79, lower-tail p = 0.29. The final polls agree slightly more than sampling alone predicts, but that is not significant.
- M1, the structural arm, gave P = 0.94 with median 51.5. Its noise model, built from cross-switching and turnout, is narrow by construction. Read its median, not its probability.
