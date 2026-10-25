#!/usr/bin/env python3
"""Checks that this repository still matches the forecast sealed before the polls closed.

Standard library only, so it runs anywhere with Python 3.9+:

    python3 verify.py            # offline checks
    python3 verify.py --online   # also fetches the Internet Archive capture of the sealed hash

Exit code 0 means every check passed. The Bitcoin timestamp is checked separately with the
OpenTimestamps client (instructions are printed at the end).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "proof" / "independent_evidence.json"
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


def check_bundle(evidence: dict) -> None:
    print("Sealed bundle (prereg/BUNDLE.sha256)")
    sealed = evidence["bundle_digest_sha256"]
    report(sha256(ROOT / "prereg" / "BUNDLE.sha256") == sealed, "bundle file hashes to the sealed digest", sealed)
    changed = documented_changes()
    for digest, name in read_checklist(ROOT / "prereg" / "BUNDLE.sha256"):
        path = ROOT / name
        actual = sha256(path) if path.exists() else "missing"
        if actual == digest:
            report(True, name)
        elif name in changed and changed[name] == (digest, actual):
            print(f"  [ok] {name}: changed for publication, documented in SANITIZED.md (sealed hash {digest[:12]}...)")
        else:
            report(False, name, f"expected {digest[:12]}..., found {actual[:12]}...")


def check_online(evidence: dict) -> None:
    print("Independent pre-deadline evidence (Internet Archive)")
    deadline = datetime.fromisoformat(evidence["deadline_utc"].replace("Z", "+00:00"))
    for capture in evidence["captures"]:
        url = capture["url"]
        captured = datetime.strptime(re.search(r"/web/(\d{14})/", url).group(1), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        raw_url = re.sub(r"/web/(\d{14})/", r"/web/\1id_/", url)
        try:
            with urllib.request.urlopen(urllib.request.Request(raw_url, headers={"User-Agent": "verify.py"}), timeout=60) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip" or body[:2] == b"\x1f\x8b":
                    body = gzip.decompress(body)
        except Exception as exc:  # network trouble is reported, not hidden
            report(False, f"fetch {url}", str(exc))
            continue
        report(evidence["bundle_digest_sha256"].encode() in body, f"capture contains the sealed digest ({url})")
        hours = (deadline - captured).total_seconds() / 3600
        report(captured < deadline, "capture time is before the polls closed", f"{captured:%Y-%m-%d %H:%M:%S} UTC, {hours:.1f} h before")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--online", action="store_true", help="also fetch the archived capture of the sealed digest")
    args = parser.parse_args()
    evidence = json.loads(EVIDENCE.read_text())
    check_data()
    check_bundle(evidence)
    if args.online:
        check_online(evidence)
    print()
    print("Bitcoin timestamp: install the OpenTimestamps client (pip install opentimestamps-client) and run")
    print("  ots verify prereg/BUNDLE.sha256.ots   (needs access to a Bitcoin node), or upload both files at")
    print("  https://opentimestamps.org to check the attestation in blocks 973010 and 973014 in a browser.")
    print()
    print("RESULT:", "all checks passed" if not FAILED else f"{len(FAILED)} check(s) failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
