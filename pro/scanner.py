"""Scanner: produces O for a repository tree under a capability map C_v."""
from __future__ import annotations

from pathlib import Path

from .models import CapabilityMap, MemberObservation, Observation, Portfolio, Relations
from .runners import RUNNERS, adapter_check, sha256_of

SURFACE_DIRS = ("hostA", "hostB", "hostC")  # synthetic hosts; everything else is anchor material


def surface_class_of(path: str) -> str:
    return Path(path).suffix.lstrip(".").lower()


def scan(root: Path, P: Portfolio, R: Relations, cap: CapabilityMap) -> Observation:
    root = Path(root)
    members: dict[str, MemberObservation] = {}
    unverifiable: list[str] = []

    for rel in R.decisions:
        for m in rel.members:
            cls = surface_class_of(m.path)
            supported = cls in cap.surface_classes
            obs = MemberObservation(path=m.path, surface_class=cls, supported=supported)
            if not supported:
                unverifiable.append(m.path)
                members[m.path] = obs
                continue
            p = root / m.path
            obs.present = p.is_file()
            if obs.present:
                obs.sha256 = sha256_of(p)
                if rel.profile == "canonical-split" and rel.anchor:
                    markers = rel.scope.wiring_markers.get(cls)
                    refs, clean = adapter_check(p.read_text(encoding="utf-8", errors="replace"), cls, rel.anchor, markers)
                    obs.references_anchor, obs.remainder_clean = refs, clean
                if rel.profile == "machine-contract" and rel.scope.fixtures:
                    if cls not in cap.fixture_runners:
                        unverifiable.append(m.path)
                        obs.fixture_error = f"no fixture runner for surface class '{cls}' in C_{cap.scanner_version}"
                    else:
                        fixdir = root / rel.scope.fixtures
                        for fx in sorted(fixdir.glob("*.json")) if fixdir.is_dir() else []:
                            try:
                                obs.fixture_outputs[fx.stem] = RUNNERS[cls](p, fx)
                            except Exception as exc:  # noqa: BLE001 - recorded as evidence, not raised
                                obs.fixture_error = f"{fx.stem}: {exc}"
            members[m.path] = obs

    tree = []
    for d in SURFACE_DIRS:
        base = root / d
        if base.is_dir():
            tree.extend(str(p.relative_to(root)).replace("\\", "/") for p in base.rglob("*") if p.is_file())
    return Observation(scanner_version=cap.scanner_version, members=members, tree=sorted(tree), unverifiable=sorted(set(unverifiable)))
