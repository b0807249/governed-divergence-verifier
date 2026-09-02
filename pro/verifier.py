"""Reconciliation of P, R and O under the five invariants.

Verdict per relation and for the portfolio: PASS, FAIL or UNVERIFIABLE.
UNVERIFIABLE is never converted into PASS.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from .models import FAIL, PASS, UNVERIFIABLE, CapabilityMap, Observation, Portfolio, Relations
from .runners import masked, sha256_of, validate


@dataclass
class Finding:
    invariant: str      # coverage | no-orphans | grounding | presence-evidence | shrinkage
    verdict: str        # FAIL | UNVERIFIABLE
    subject: str        # relation id, incidence key or path
    detail: str


@dataclass
class Report:
    verdict: str
    findings: list[Finding] = field(default_factory=list)
    relation_verdicts: dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [f"verdict: {self.verdict}"]
        for f in self.findings:
            lines.append(f"  [{f.verdict}] {f.invariant}: {f.subject} -- {f.detail}")
        return "\n".join(lines)


def _expired(rel_expiry: Optional[str], today: date) -> bool:
    return bool(rel_expiry) and date.fromisoformat(rel_expiry) < today


def reconcile(root: Path, P_prev: Optional[Portfolio], P: Portfolio, R: Relations, O: Observation,
              cap: CapabilityMap, today: Optional[date] = None) -> Report:
    root = Path(root)
    today = today or date.today()
    findings: list[Finding] = []
    rel_verdicts: dict[str, str] = {}
    by_id = R.by_id()
    live = {rid: rel for rid, rel in by_id.items() if not _expired(rel.expiry, today)}
    waiver_cover: set[tuple[str, str]] = set()
    for rel in live.values():
        if rel.profile == "deliberate-singleton":
            waiver_cover.update(tuple(w) for w in rel.waives)
    member_cover: set[tuple[str, str]] = set()
    for rel in live.values():
        member_cover |= rel.member_keys()

    # 1. Coverage: every incidence in P is resolved by a live relation decision;
    #    a deliberately unsupported incidence is resolved by a non-support waiver.
    for inc in P.incidences:
        if inc.status == "supported":
            if inc.key not in member_cover:
                findings.append(Finding("coverage", FAIL, f"{inc.family}@{inc.surface}", "expected incidence has no live relation decision"))
        else:
            w = by_id.get(inc.waiver or "")
            if w is None or w.profile != "deliberate-singleton" or list(inc.key) not in [list(x) for x in w.waives]:
                findings.append(Finding("coverage", FAIL, f"{inc.family}@{inc.surface}", "non-support entry has no matching waiver decision"))
            elif inc.waiver not in live:
                findings.append(Finding("coverage", FAIL, f"{inc.family}@{inc.surface}", f"waiver {inc.waiver} expired; treated as retracted"))

    # 2. No orphans: every observed in-scope asset maps to a relation member.
    member_paths = {m.path for rel in R.decisions for m in rel.members}
    for path in O.tree:
        if path not in member_paths:
            findings.append(Finding("no-orphans", FAIL, path, "observed asset on a surface is not a member of any relation"))

    # 3. Grounding: anchors resolve consistently with the declared profile.
    for rid, rel in by_id.items():
        problems = []
        if rel.profile in ("canonical-split", "shared-engine"):
            if not rel.anchor or not (root / rel.anchor).is_file():
                problems.append(f"anchor {rel.anchor!r} does not resolve")
            elif rel.anchor_sha256 and sha256_of(root / rel.anchor) != rel.anchor_sha256:
                problems.append("anchor content differs from the declared hash")
        if rel.profile == "machine-contract":
            sp = root / (rel.scope.schema or "")
            if not rel.scope.schema or not sp.is_file():
                problems.append(f"schema {rel.scope.schema!r} does not resolve")
            else:
                declared = json.loads(sp.read_text(encoding="utf-8")).get("version")
                if rel.scope.schema_version and declared != rel.scope.schema_version:
                    problems.append(f"schema version {declared!r} != declared {rel.scope.schema_version!r}")
            fx = root / (rel.scope.fixtures or "")
            if not rel.scope.fixtures or not fx.is_dir() or not any(fx.glob("*.json")):
                problems.append(f"fixture set {rel.scope.fixtures!r} does not resolve")
        if rel.profile == "deliberate-singleton" and not rel.waives:
            problems.append("waiver names no incidence")
        if not rel.owner:
            problems.append("no owner named")
        if _expired(rel.expiry, today):
            problems.append(f"decision expired on {rel.expiry}; treated as retracted")
        for pr in problems:
            findings.append(Finding("grounding", FAIL, rid, pr))
        if problems:
            rel_verdicts[rid] = FAIL

    # 4. Presence and evidence: members present and the selected assurance holds;
    #    unsupported observation is UNVERIFIABLE, never PASS.
    for rid, rel in by_id.items():
        if rel_verdicts.get(rid) == FAIL:
            continue
        verdict = PASS
        for m in rel.members:
            obs = O.members.get(m.path)
            if obs is None or not obs.supported:
                findings.append(Finding("presence-evidence", UNVERIFIABLE, m.path, f"surface class outside C_{cap.scanner_version}"))
                verdict = UNVERIFIABLE if verdict != FAIL else FAIL
                continue
            if not obs.present:
                findings.append(Finding("presence-evidence", FAIL, m.path, "required member is absent"))
                verdict = FAIL
                continue
            if rel.profile == "canonical-split":
                if not obs.references_anchor:
                    findings.append(Finding("presence-evidence", FAIL, m.path, "adapter does not reference the canonical anchor"))
                    verdict = FAIL
                elif not obs.remainder_clean:
                    findings.append(Finding("presence-evidence", FAIL, m.path, "adapter has content outside declared host-wiring regions"))
                    verdict = FAIL
            if rel.profile == "machine-contract" and obs.fixture_error and not obs.fixture_outputs:
                if "no fixture runner" in obs.fixture_error:
                    findings.append(Finding("presence-evidence", UNVERIFIABLE, m.path, obs.fixture_error))
                    verdict = UNVERIFIABLE if verdict != FAIL else FAIL
                else:
                    findings.append(Finding("presence-evidence", FAIL, m.path, obs.fixture_error))
                    verdict = FAIL
        if rel.profile == "machine-contract" and verdict == PASS:
            schema = json.loads((root / rel.scope.schema).read_text(encoding="utf-8"))
            outputs = {m.path: O.members[m.path].fixture_outputs for m in rel.members}
            fixtures = sorted({fx for outs in outputs.values() for fx in outs})
            for fx in fixtures:
                reports = {}
                for path, outs in outputs.items():
                    rep = outs.get(fx)
                    if rep is None:
                        findings.append(Finding("presence-evidence", FAIL, path, f"fixture {fx}: no output"))
                        verdict = FAIL
                        continue
                    errs = validate(rep, schema)
                    if errs:
                        findings.append(Finding("presence-evidence", FAIL, path, f"fixture {fx}: schema violation: {'; '.join(errs)}"))
                        verdict = FAIL
                    reports[path] = masked(rep, rel.scope.volatile)
                if len(reports) == len(outputs) and len({json.dumps(r, sort_keys=True) for r in reports.values()}) > 1:
                    findings.append(Finding("presence-evidence", FAIL, rid, f"fixture {fx}: members differ inside the scope after masking {rel.scope.volatile}"))
                    verdict = FAIL
        rel_verdicts[rid] = verdict

    # 5. Waiver-gated shrinkage: removed incidences need a waiver in R_{t+1}.
    if P_prev is not None:
        for key, inc in P_prev.by_key().items():
            if inc.status != "supported":
                continue
            now = P.by_key().get(key)
            if now is None or now.status != "supported":
                if key not in waiver_cover:
                    findings.append(Finding("shrinkage", FAIL, f"{key[0]}@{key[1]}",
                                            f"support removed between P v{P_prev.version} and P v{P.version} without a waiver"))

    overall = PASS
    if any(f.verdict == FAIL for f in findings):
        overall = FAIL
    elif any(f.verdict == UNVERIFIABLE for f in findings):
        overall = UNVERIFIABLE
    return Report(overall, findings, rel_verdicts)
