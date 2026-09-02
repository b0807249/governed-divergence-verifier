"""Assurance mechanisms used by the scanner.

- masked comparison for canonical-split adapters (host-wiring regions are hidden)
- a tiny JSON-schema subset validator for machine contracts
- fixture runners for the synthetic 'report' behaviour: an imperative Python
  implementation (host A) and a declarative TOML implementation (host B)
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

REFERENCE_PATTERNS = {
    # surface class -> how an adapter references the canonical anchor
    "md": "@include {anchor}",
    "toml": 'include = "{anchor}"',
    "yaml": "include: {anchor}",
}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_text(text: str) -> str:
    """Normalisation applied before masked comparison: line endings and trailing whitespace."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(ln.rstrip() for ln in lines).strip("\n")


def mask_wiring(text: str, markers: list[str] | None) -> str:
    """Remove host-wiring regions delimited by the given start/end marker lines."""
    if not markers:
        return normalize_text(text)
    start, end = markers
    out, hiding = [], False
    for ln in normalize_text(text).split("\n"):
        s = ln.strip()
        if s == start:
            hiding = True
            continue
        if s == end:
            hiding = False
            continue
        if not hiding:
            out.append(ln)
    return "\n".join(out).strip("\n")


def adapter_check(text: str, surface_class: str, anchor: str, markers: list[str] | None) -> tuple[bool, bool]:
    """Return (references_anchor, remainder_clean) for a canonical-split adapter."""
    remainder = mask_wiring(text, markers)
    expected = REFERENCE_PATTERNS.get(surface_class, "{anchor}").format(anchor=anchor)
    lines = [ln for ln in remainder.split("\n") if ln.strip()]
    references = any(ln.strip() == expected for ln in lines)
    clean = references and len(lines) == 1
    return references, clean


# ---------------------------------------------------------------- schema
def validate(report: dict, schema: dict) -> list[str]:
    """JSON-schema subset: type object, required, properties{enum,type}, additionalProperties."""
    errors = []
    if not isinstance(report, dict):
        return ["report is not an object"]
    for key in schema.get("required", []):
        if key not in report:
            errors.append(f"missing required field '{key}'")
    props = schema.get("properties", {})
    for key, value in report.items():
        if key not in props:
            if schema.get("additionalProperties", True) is False:
                errors.append(f"unexpected field '{key}'")
            continue
        spec = props[key]
        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"field '{key}' value {value!r} not in {spec['enum']}")
        t = spec.get("type")
        if t == "array" and not isinstance(value, list):
            errors.append(f"field '{key}' is not an array")
        if t == "string" and not isinstance(value, str):
            errors.append(f"field '{key}' is not a string")
    return errors


def masked(report: dict, volatile: list[str]) -> dict:
    return {k: v for k, v in report.items() if k not in volatile}


# ---------------------------------------------------------------- runners
def run_py(script: Path, fixture: Path) -> dict:
    proc = subprocess.run([sys.executable, str(script), str(fixture)], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"exit {proc.returncode}: {proc.stderr.strip()[:200]}")
    return json.loads(proc.stdout)


def run_toml(config: Path, fixture: Path) -> dict:
    """Declarative host: the config names thresholds and labels; the runner supplies control flow."""
    cfg = tomllib.loads(config.read_text(encoding="utf-8"))
    section = cfg.get("report", {})
    data = json.loads(fixture.read_text(encoding="utf-8"))
    warnings = int(data.get("warnings", 0))
    # two accepted spellings of the threshold, so a reimplementation can differ inside the scope
    threshold = section.get("warn_if_warnings_gt")
    if threshold is None:
        threshold = section.get("threshold", {}).get("warnings", 0)
    status = section.get("status_warn", "warn") if warnings > int(threshold) else section.get("status_ok", "ok")
    findings = [section.get("finding_template", "warnings={warnings}").format(warnings=warnings)] if warnings > int(threshold) else []
    report = {"status": status, "findings": findings,
              "timestamp": datetime.now(timezone.utc).isoformat(), "host_id": section.get("host_id", "B")}
    for extra_key, extra_val in section.get("extra_fields", {}).items():
        report[extra_key] = extra_val
    return report


RUNNERS = {"py": run_py, "toml": run_toml}
