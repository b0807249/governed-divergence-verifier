"""Baseline B4.3: fan-out generator + versioned target manifest + hash-drift checker
+ structured expiring waivers.  No independent reconciliation of P, R and O.

Frozen semantics (this is the comparator the paper names, not a straw man):
- the manifest lists target paths with the hash each should have, plus a version number;
- the checker compares the CURRENT tree against the CURRENT manifest: a listed target that is
  missing or whose hash differs is a drift, unless an unexpired waiver names that path;
- manifest edits are ordinary edits; nothing compares manifest v_t with v_{t+1};
- files on a surface that the manifest does not list are ignored (a fan-out generator would
  regenerate its own targets and does not police unrelated files).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

PASS, FAIL = "PASS", "FAIL"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class BaselineReport:
    verdict: str
    drifts: list[str] = field(default_factory=list)
    waived: list[str] = field(default_factory=list)


def fan_out(root: Path, canonical: str, targets: dict[str, str]) -> None:
    """Generate adapter files from a canonical file and per-surface wiring templates."""
    for rel_path, template in targets.items():
        (root / rel_path).parent.mkdir(parents=True, exist_ok=True)
        (root / rel_path).write_text(template.format(anchor=canonical), encoding="utf-8", newline="\n")


def write_manifest(root: Path, version: int, target_paths: list[str], manifest_path: str = "baseline/manifest.json") -> None:
    targets = [{"path": p, "sha256": sha256_of(root / p)} for p in target_paths]
    (root / manifest_path).parent.mkdir(parents=True, exist_ok=True)
    (root / manifest_path).write_text(json.dumps({"version": version, "targets": targets}, indent=2), encoding="utf-8")


def check(root: Path, manifest_path: str = "baseline/manifest.json", waivers_path: str = "baseline/waivers.json",
          today: Optional[date] = None) -> BaselineReport:
    root, today = Path(root), today or date.today()
    manifest = json.loads((root / manifest_path).read_text(encoding="utf-8"))
    waivers = []
    if (root / waivers_path).is_file():
        waivers = json.loads((root / waivers_path).read_text(encoding="utf-8"))
    active = {w["path"] for w in waivers if not w.get("expires") or date.fromisoformat(w["expires"]) >= today}
    drifts, waived = [], []
    for t in manifest["targets"]:
        p = root / t["path"]
        ok = p.is_file() and sha256_of(p) == t["sha256"]
        if ok:
            continue
        if t["path"] in active:
            waived.append(t["path"])
        else:
            drifts.append(t["path"])
    return BaselineReport(FAIL if drifts else PASS, drifts, waived)
