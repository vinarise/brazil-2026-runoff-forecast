#!/usr/bin/env python3
"""Checks that this repository still matches the forecast sealed before the polls closed.

Standard library only, so it runs anywhere with Python 3.9+:

    python3 verify.py            # offline checks
    python3 verify.py --online   # also fetches the Internet Archive captures of the sealed hash

Exit code 0 means every check passed. The Bitcoin merkle path inside the OpenTimestamps proof is
checked separately with the OpenTimestamps client (instructions are printed at the end).
"""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "proof" / "independent_evidence.json"
BUNDLE = ROOT / "prereg" / "BUNDLE.sha256"
OTS = ROOT / "prereg" / "BUNDLE.sha256.ots"
FROZEN = ROOT / "prereg" / "forecast_frozen.json"
BUILDER = ROOT / "src" / "build_forecast_notebook.py"
NOTEBOOK = ROOT / "notebooks" / "01_forecast.executed.ipynb"
# Only a rendering may differ from its sealed bytes, and only when SANITIZED.md documents it. The
# pre-registration, the data manifest, the frozen forecast, the ledger and the code never may.
SANITIZABLE = ("notebooks/",)
FAILED: list[str] = []


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report(ok: bool, what: str, detail: str = "") -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {what}" + (f": {detail}" if detail else ""))
    if not ok:
        FAILED.append(what)


def read_checklist(path: Path) -> list[tuple[str, str]]:
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            rows.append((digest, name.lstrip("*")))
    return rows


def documented_changes() -> dict[str, tuple[str, str]]:
    """Files changed for publication, from SANITIZED.md: name -> (frozen sha256, published sha256)."""
    path = ROOT / "SANITIZED.md"
    if not path.exists():
        return {}
    rows = re.findall(r"^\| `([^`]+)` \| `([0-9a-f]{64})` \| `([0-9a-f]{64})` \|", path.read_text(), re.M)
    return {name: (frozen, published) for name, frozen, published in rows}


def check_data() -> None:
    print("Frozen poll snapshot (prereg/data_manifest.sha256)")
    for digest, name in read_checklist(ROOT / "prereg" / "data_manifest.sha256"):
        path = ROOT / "data" / "raw" / name
        report(path.exists() and sha256(path) == digest, f"data/raw/{name}")


def check_bundle(evidence: dict) -> tuple[set[str], list[str]]:
    """Returns (files identical to the sealed bytes, files accepted on SANITIZED.md documentation)."""
    print("Sealed bundle (prereg/BUNDLE.sha256)")
    sealed = evidence["bundle_digest_sha256"]
    report(sha256(BUNDLE) == sealed, "bundle file hashes to the sealed digest", sealed)
    changed = documented_changes()
    identical: set[str] = set()
    accepted: list[str] = []
    for digest, name in read_checklist(BUNDLE):
        path = ROOT / name
        actual = sha256(path) if path.exists() else "missing"
        if actual == digest:
            report(True, name)
            identical.add(name)
        elif name in changed and changed[name] == (digest, actual) and name.startswith(SANITIZABLE):
            print(f"  [ok*] {name}: not the sealed bytes; the published copy is documented in SANITIZED.md "
                  f"(sealed {digest[:12]}..., published {actual[:12]}...) and is checked against the sealed sources below")
            accepted.append(name)
        else:
            report(False, name, f"expected {digest[:12]}..., found {actual[:12]}...")
    return identical, accepted


def varuint(data: bytes, pos: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return value, pos


def check_ots(evidence: dict) -> None:
    """The proof file commits to the sealed digest and carries Bitcoin block attestations (merkle path not checked here)."""
    print("OpenTimestamps proof (prereg/BUNDLE.sha256.ots)")
    data = OTS.read_bytes()
    magic = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94"
    if not data.startswith(magic):
        report(False, "proof file has the OpenTimestamps header")
        return
    _version, pos = varuint(data, len(magic))
    op = data[pos]
    digest = data[pos + 1:pos + 33].hex()
    report(op == 0x08 and digest == evidence["bundle_digest_sha256"], "proof commits to the sealed digest (sha256)", digest)
    tag = bytes.fromhex("0588960d73d71901")  # BitcoinBlockHeaderAttestation
    heights = []
    i = data.find(tag)
    while i >= 0:
        _length, pos = varuint(data, i + len(tag))
        height, _ = varuint(data, pos)
        heights.append(height)
        i = data.find(tag, i + 1)
    report(bool(heights), "proof carries Bitcoin block attestations",
           f"blocks {sorted(heights)}; the merkle path needs `ots verify` or a block explorer, see below")


def builder_cells(path: Path) -> list[tuple[str, str]]:
    """The (cell_type, source) list the sealed notebook builder generates, read from its source with ast."""
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.List) and any(
                isinstance(t, ast.Attribute) and t.attr == "cells" for t in node.targets):
            cells = []
            for el in node.value.elts:
                if not (isinstance(el, ast.Call) and isinstance(el.func, ast.Name) and el.func.id in ("md", "code")
                        and len(el.args) == 1 and isinstance(el.args[0], ast.Constant)):
                    raise ValueError("unexpected cell expression in the notebook builder")
                cells.append(("markdown" if el.func.id == "md" else "code", el.args[0].value))
            return cells
    raise ValueError("no cells assignment in the notebook builder")


def text(value) -> str:
    return "".join(value) if isinstance(value, list) else str(value or "")


def check_notebook_rendering() -> None:
    """The published notebook is what the sealed builder generates, and it prints the sealed forecast."""
    print("Published forecast notebook against the sealed sources")
    cells = json.loads(NOTEBOOK.read_text())["cells"]
    expected = builder_cells(BUILDER)
    same = len(cells) == len(expected) and all(
        c["cell_type"] == kind and text(c.get("source")) == source for c, (kind, source) in zip(cells, expected))
    report(same, "every cell's source is what the sealed src/build_forecast_notebook.py generates", f"{len(cells)} cells")
    frozen = json.loads(FROZEN.read_text())
    keys = ("p_flavio", "p_lula", "median_flavio_vv", "pi80", "pi95", "market_comparator_p_flavio")
    printed = json.dumps({k: frozen[k] for k in keys}, indent=2)
    outputs = "".join(text(o.get("text")) for c in cells for o in c.get("outputs", []) if o.get("output_type") == "stream")
    report(printed in outputs, "the forecast the notebook prints equals the sealed prereg/forecast_frozen.json")


def fetch(url: str, attempts: int = 3):
    """Returns (body, headers, final url). Network trouble is retried, then reported, never hidden."""
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "verify.py (brazil-2026-runoff-forecast)"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip" or body[:2] == b"\x1f\x8b":
                    body = gzip.decompress(body)
                return body, resp.headers, resp.geturl()
        except Exception as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"{last} after {attempts} attempts")


def archive_time(headers, final_url: str):
    """The capture time the archive itself reports: the Memento-Datetime header, else the final URL's timestamp."""
    memento = headers.get("Memento-Datetime")
    if memento:
        return parsedate_to_datetime(memento).astimezone(timezone.utc)
    m = re.search(r"/web/(\d{14})", final_url)
    return datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc) if m else None


def check_online(evidence: dict) -> None:
    print("Independent pre-deadline evidence (Internet Archive)")
    deadline = datetime.fromisoformat(evidence["deadline_utc"].replace("Z", "+00:00"))
    for capture in evidence["captures"]:
        url = capture["url"]
        claimed = datetime.strptime(re.search(r"/web/(\d{14})/", url).group(1), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        raw_url = re.sub(r"/web/(\d{14})/", r"/web/\1id_/", url)
        try:
            body, headers, final_url = fetch(raw_url)
        except Exception as exc:
            report(False, f"fetch {url}", str(exc))
            continue
        report(evidence["bundle_digest_sha256"].encode() in body, f"capture contains the sealed digest ({url})")
        archived = archive_time(headers, final_url)
        if archived is None:
            report(False, "the archive reports the capture time", "no Memento-Datetime header and no timestamp in the final URL")
            continue
        hours = (deadline - archived).total_seconds() / 3600
        report(archived < deadline, "the archive's own capture time is before the polls closed",
               f"{archived:%Y-%m-%d %H:%M:%S} UTC, {hours:.1f} h before")
        report(abs((archived - claimed).total_seconds()) <= 60, "the archive's capture time matches proof/independent_evidence.json",
               f"archive {archived:%H:%M:%S} UTC, file {claimed:%H:%M:%S} UTC")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--online", action="store_true", help="also fetch the archived captures of the sealed digest")
    args = parser.parse_args()
    evidence = json.loads(EVIDENCE.read_text())
    check_data()
    identical, accepted = check_bundle(evidence)
    check_ots(evidence)
    if {"src/build_forecast_notebook.py", "prereg/forecast_frozen.json"} <= identical:
        check_notebook_rendering()
    else:
        print("Published forecast notebook: skipped, the sealed builder or forecast record did not verify")
    if args.online:
        check_online(evidence)
    print()
    if accepted:
        print(f"Note: {', '.join(accepted)} is published with one string replaced (see SANITIZED.md), so its")
        print("  sealed hash can only be checked against the original file, which is available on request. Its cells")
        print("  and the forecast it prints were checked above against the sealed builder and the sealed forecast record.")
    print("Bitcoin merkle path: pip install opentimestamps-client, then `ots verify prereg/BUNDLE.sha256.ots` (needs a")
    print("  Bitcoin node), or `ots -v --no-bitcoin verify prereg/BUNDLE.sha256.ots` prints the merkle root to compare")
    print("  with any block explorer for blocks 973010 and 973014, or upload both files at https://opentimestamps.org.")
    print()
    print("RESULT:", "all checks passed" if not FAILED else f"{len(FAILED)} check(s) failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
