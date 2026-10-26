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


def url(election: int, uf: str = "br", mun: str = "") -> str:
    """National, state (uf) or municipality (uf + 5-digit TSE code in mun) results file."""
    return f"{BASE}/{election}/dados/{uf}/{uf}{mun}-c0001-e00{election}-u.jws"


def config_url(election: int) -> str:
    """Municipality list for one election (capital flag `c`, TSE code `cd`, IBGE code `cdi`)."""
    return f"{BASE}/{election}/config/mun-e00{election}-cm.json"


def decode(jws: str) -> dict:
    payload = jws.strip().split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def num(x: str) -> float:
    return float(str(x).replace(",", "."))


def _get(u: str) -> str:
    req = urllib.request.Request(u, headers={"User-Agent": "vina-forecasts (research)"})
    return urllib.request.urlopen(req, timeout=30).read().decode()


def _save(election: int, name: str, raw: str, ext: str) -> None:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = SNAP / str(election); d.mkdir(parents=True, exist_ok=True)
    f = d / f"{name}-{stamp}.{ext}"
    f.write_text(raw)
    with open(d / "SHA256SUMS", "a") as h:
        h.write(f"{hashlib.sha256(raw.encode()).hexdigest()}  {f.name}\n")


def fetch(election: int, uf: str = "br", save: bool = True, mun: str = "") -> dict:
    raw = _get(url(election, uf, mun))
    data = decode(raw)
    if save:
        _save(election, f"{uf}{mun}", raw, "jws")
    return data


def fetch_config(election: int, save: bool = True) -> dict:
    raw = _get(config_url(election))
    if save:
        _save(election, "mun-cm", raw, "json")
    return json.loads(raw)


def load_saved(election: int, name: str, ext: str = "jws") -> dict:
    """The most recent saved snapshot of one file (name = uf, uf + mun, or "mun-cm"), for offline re-runs."""
    files = sorted((SNAP / str(election)).glob(f"{name}-*.{ext}"))
    if not files:
        raise FileNotFoundError(f"no saved snapshot {name} for election {election} under {SNAP}")
    raw = files[-1].read_text()
    return decode(raw) if ext == "jws" else json.loads(raw)


def summary(p: dict) -> dict:
    """Two-candidate totals and the counting status from one decoded payload."""
    cands = {c["n"]: c for a in p["carg"][0]["agr"] for par in a["par"] for c in par["cand"]}
    f, l = num(cands[FLAVIO]["vap"]), num(cands[LULA]["vap"])
    return {"scope": p.get("cdabr"), "generated": f"{p.get('dg')} {p.get('hg')}",
            "pct_sections": num(p["s"]["pst"]), "final": p.get("tf") == "s",
            "flavio_votes": f, "lula_votes": l, "valid": num(p["v"]["vv"]),
            "turnout": num(p["e"]["c"]), "electorate": num(p["e"]["te"]),
            "electorate_counted": num(p["e"].get("est", p["e"]["te"])),
            "total_votes": num(p["v"]["tv"]), "blank": num(p["v"]["vb"]), "null": num(p["v"]["tvn"]),
            "flavio_two_party": 100 * f / (f + l) if f + l else float("nan")}


def candidate_votes(p: dict) -> dict:
    """Votes by ballot number (str) for every candidate in one decoded payload."""
    return {c["n"]: num(c["vap"]) for a in p["carg"][0]["agr"] for par in a["par"] for c in par["cand"]}
