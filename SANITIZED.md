# Files changed for publication

Notebook outputs contained a software warning that printed the machine's home path. In the published copies
that path is replaced by `~/`. Nothing else changed. Hashes before and after:

| File | sha256 as frozen | sha256 as published | In the sealed bundle |
|---|---|---|---|
| `notebooks/01_forecast.executed.ipynb` | `89b9e3202a0702cd5aaeda63f84076e5379a6ca33a0cce0f939e3d259092f6e0` | `4d13fbc6e45013cb9914d0db1f1d2eaca9b6e60d396aaa80bdba76b91293da58` | yes |
| `notebooks/01_forecast.html` | `d1c7abf2ef049fc28542d0ba5920a664c50fc6e66e42db3b3e4f9587e2c2f564` | `1f84f63e4b94dfc99cadaf61462cd4c852c98d7b008a7954039b91d50e1fc8cb` | no |
| `notebooks/02_polarization.executed.ipynb` | `02c3f6187f1445d4ad54248910a3b1a89c615847c05962c06ade4f467b578dba` | `64aac0f8292e163f902e48cace0f489dacb866046029c4f213d8ef00bf3c0f35` | no |
| `notebooks/02_polarization.html` | `b72f10054986f1729c80c4fb74bb1a92a6c8efd83e0daadfb0a96d405d4c1043` | `16a4dd5a936554ffa5b3e35f4a7bb68597237ad117f0a68ce7c801652ef324aa` | no |

For a bundle file listed above, `sha256sum -c prereg/BUNDLE.sha256` reports that one file as changed, and the
frozen hash in the first column is the one the seal covers. `verify.py` accepts exactly these documented
changes and nothing else. Every other bundle file, including the frozen forecast record
(`prereg/forecast_frozen.json`), the ledger and the code, verifies unchanged. The scoring notebook re-runs the
frozen model and asserts that it reproduces the frozen probabilities.
