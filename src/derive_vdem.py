"""Fetches V-Dem v16 at a pinned commit, verifies it, and writes the small derived tables Part B uses.

The 34 MB source is not committed; the derived CSVs are. Re-run to reproduce them byte for byte.
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadr

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "data" / "external"
OUT = ROOT / "data" / "derived"
COMMIT = "f4dd26922e658442524dfd954bf14f7ebe622d5d"   # vdeminstitute/vdemdata, 2026-03-17 (V-Dem v16)
URL = f"https://raw.githubusercontent.com/vdeminstitute/vdemdata/{COMMIT}/data/vdem.RData"
SHA256 = "39b412d39a061c18f20c98e4ad4d6355b05a0441df31be4ee9aec420dc3d95ea"
HOSTILE = 1.34   # v2cacamps interval value at the lower edge of ordinal 4, "hostile camps" (Codebook v16)


def fetch() -> Path:
    EXT.mkdir(parents=True, exist_ok=True)
    path = EXT / "vdem.RData"
    if not path.exists():
        urllib.request.urlretrieve(URL, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != SHA256:
        sys.exit(f"vdem.RData sha256 {digest} != pinned {SHA256}")
    return path


def main() -> None:
    df = list(pyreadr.read_r(fetch()).values())[0]
    OUT.mkdir(parents=True, exist_ok=True)
    keep = ["country_name", "country_text_id", "year", "e_regionpol_6C", "e_pop", "v2x_regime",
            "v2cacamps", "v2cacamps_codelow", "v2cacamps_codehigh", "v2cacamps_nr",
            "v2smpolsoc", "v2smpolsoc_codelow", "v2smpolsoc_codehigh", "v2smpolsoc_nr"]
    pol = df.loc[df["year"] >= 1990, keep].copy()
    pol["year"] = pol["year"].astype(int)
    pol.to_csv(OUT / "vdem_polarization_1990_2025.csv", index=False, float_format="%.4f")

    # Presidential elections: vote share of the largest and second-largest vote-getter
    # (first round where there are two). Margin = largest - second, in points.
    el = df.loc[(df["year"] >= 1990) & df["v2elvotlrg"].notna() & df["v2elvotsml"].notna(),
                ["country_name", "country_text_id", "year", "v2x_regime", "v2elvotlrg", "v2elvotsml",
                 "v2eltype_6", "v2eltype_7"]].copy()
    el["year"] = el["year"].astype(int)
    el["margin_pp"] = (el["v2elvotlrg"] - el["v2elvotsml"]).abs()
    el.to_csv(OUT / "vdem_presidential_margins_1990_2025.csv", index=False, float_format="%.4f")
    print(len(pol), "country-years;", len(el), "presidential elections")


if __name__ == "__main__":
    main()
