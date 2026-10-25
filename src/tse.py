"""Official results from resultados.tse.jus.br (signed JWS). Every fetch is saved raw with its hash.

The signature is not verified (TSE's public key for this kid was not located); the payload is
cross-checked against press totals in the scoring notebook instead.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "result"
BASE = "https://resultados.tse.jus.br/oficial/ele2026"
RUNOFF, FIRST = 6258, 6257
FLAVIO, LULA = "22", "13"
UFS = ("ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to zz").split()


def url(election: int, uf: str = "br") -> str:
    return f"{BASE}/{election}/dados/{uf}/{uf}-c0001-e00{election}-u.jws"


def decode(jws: str) -> dict:
    payload = jws.strip().split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def num(x: str) -> float:
    return float(str(x).replace(",", "."))


def fetch(election: int, uf: str = "br", save: bool = True) -> dict:
    req = urllib.request.Request(url(election, uf), headers={"User-Agent": "vina-forecasts (research)"})
    raw = urllib.request.urlopen(req, timeout=30).read().decode()
    data = decode(raw)
    if save:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        d = SNAP / str(election); d.mkdir(parents=True, exist_ok=True)
        f = d / f"{uf}-{stamp}.jws"
        f.write_text(raw)
        with open(d / "SHA256SUMS", "a") as h:
            h.write(f"{hashlib.sha256(raw.encode()).hexdigest()}  {f.name}\n")
    return data


def summary(p: dict) -> dict:
    """Two-candidate totals and the counting status from one decoded payload."""
    cands = {c["n"]: c for a in p["carg"][0]["agr"] for par in a["par"] for c in par["cand"]}
    f, l = num(cands[FLAVIO]["vap"]), num(cands[LULA]["vap"])
    return {"scope": p.get("cdabr"), "generated": f"{p.get('dg')} {p.get('hg')}",
            "pct_sections": num(p["s"]["pst"]), "final": p.get("tf") == "s",
            "flavio_votes": f, "lula_votes": l, "valid": num(p["v"]["vv"]),
            "turnout": num(p["e"]["c"]), "electorate": num(p["e"]["te"]),
            "flavio_two_party": 100 * f / (f + l) if f + l else float("nan")}
