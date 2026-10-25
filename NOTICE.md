# Third-party data

| Data | Where | Source and terms |
|---|---|---|
| V-Dem Dataset v16 (derived tables only) | `data/derived/` | Coppedge, Michael, John Gerring, Carl Henrik Knutsen, Staffan I. Lindberg, Jan Teorell, et al. (2026). "V-Dem Country-Year Dataset v16". Varieties of Democracy (V-Dem) Project. https://doi.org/10.23696/vdemds26. V-Dem asks that reuse also cite its measurement model: Pemstein, Daniel, Kyle L. Marquardt, Eitan Tzelgov, Yi-ting Wang, Juraj Medzihorsky, Joshua Krusell, Farhad Miri and Johannes von Römer (2026). "The V-Dem Measurement Model: Latent Variable Analysis for Cross-National and Cross-Temporal Expert-Coded Data". V-Dem Working Paper No. 21, the edition that accompanies v16. The source file was fetched from the `vdemdata` R package at commit `f4dd269`, with its sha256 pinned in `src/derive_vdem.py`. Used under the V-Dem Project's terms of use; the raw dataset is not redistributed here, only these derived tables. |
| Official election results | `data/raw/`, `data/backtest/`, `data/result/` | Tribunal Superior Eleitoral (TSE), public result files and open data portal. |
| Published opinion polls | `data/raw/polls_2026_r2.csv` and related files | Compiled from public reports; each row carries its TSE registration number and source URL. The pollsters own their surveys. |
| Prediction-market prices | `data/raw/markets_2026.csv` | Public prices as reported; used only as a comparator. |
