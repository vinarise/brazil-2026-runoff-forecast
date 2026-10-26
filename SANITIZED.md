# Files changed for publication

Notebook outputs contained a software warning that printed the machine's home path. In the published copies
that path is replaced by `~/`. Nothing else changed. Hashes before and after:

| File | sha256 as frozen | sha256 as published | In the sealed bundle |
|---|---|---|---|
| `notebooks/01_forecast.executed.ipynb` | `89b9e3202a0702cd5aaeda63f84076e5379a6ca33a0cce0f939e3d259092f6e0` | `4d13fbc6e45013cb9914d0db1f1d2eaca9b6e60d396aaa80bdba76b91293da58` | yes |
| `notebooks/01_forecast.html` | `d1c7abf2ef049fc28542d0ba5920a664c50fc6e66e42db3b3e4f9587e2c2f564` | `1f84f63e4b94dfc99cadaf61462cd4c852c98d7b008a7954039b91d50e1fc8cb` | no |
| `notebooks/02_polarization.executed.ipynb` | `02c3f6187f1445d4ad54248910a3b1a89c615847c05962c06ade4f467b578dba` | `64aac0f8292e163f902e48cace0f489dacb866046029c4f213d8ef00bf3c0f35` | no |
| `notebooks/02_polarization.html` | `b72f10054986f1729c80c4fb74bb1a92a6c8efd83e0daadfb0a96d405d4c1043` | `16a4dd5a936554ffa5b3e35f4a7bb68597237ad117f0a68ce7c801652ef324aa` | no |
| `notebooks/03_scoring.executed.ipynb` | `fdab2c810b343f74ed17ec06319617ce8874463d26f3e1a0abb11c76517b2d76` | `84c4e67056eecd8cd53a4c3912c37b575a6a490c40a512056354418ed48401d3` | no |

For a bundle file listed above, `sha256sum -c prereg/BUNDLE.sha256` reports that one file as changed, and the
frozen hash in the first column is the one the seal covers. This file is not itself sealed, so `verify.py` does
not take it on trust alone: it accepts a documented change only for a notebook rendering, never for the
pre-registration, the data manifest, the frozen forecast record, the ledger or the code, and it checks the
published forecast notebook against the sealed sources (every cell is what the sealed
`src/build_forecast_notebook.py` generates, and the forecast it prints equals the sealed
`prereg/forecast_frozen.json`). What no check can do without the original path is recompute the sealed hash;
the original file is available on request (vina@vinarise.com). Every other bundle file verifies unchanged.
