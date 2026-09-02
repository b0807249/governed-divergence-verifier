"""Governance objects of the Governed Divergence model: P, R and O.

This is the toy verifier that accompanies the JSS New Ideas and Trends
paper.  It exists to show that the definitions in the paper are executable
and that they give different verdicts from a manifest-and-hash baseline on
a handful of synthetic cases.  It is an illustration, not an evaluation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

PASS, FAIL, UNVERIFIABLE = "PASS", "FAIL", "UNVERIFIABLE"

PROFILES = ("canonical-split", "shared-engine", "machine-contract", "manual-sync", "deliberate-singleton")


@dataclass
class Incidence:
    """One (family, surface) pair listed in P.

    status is "supported" or "unsupported"; an unsupported incidence must
    point to a non-support waiver decision in R by its id.
    """
    family: str
    surface: str
    status: str = "supported"
    waiver: Optional[str] = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.family, self.surface)


@dataclass
class Portfolio:
    version: int
    incidences: list[Incidence]

    def by_key(self) -> dict[tuple[str, str], Incidence]:
        return {i.key: i for i in self.incidences}

    @staticmethod
    def load(path: Path) -> "Portfolio":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return Portfolio(raw["version"], [Incidence(**i) for i in raw["incidences"]])

    def dump(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


@dataclass
class Member:
    family: str
    surface: str
    path: str  # repo-relative path of the concrete asset on that surface

    @property
    def key(self) -> tuple[str, str]:
        return (self.family, self.surface)


@dataclass
class Scope:
    """What a relation's assurance examines; anything else is not examined."""
    schema: Optional[str] = None          # repo-relative path of a JSON schema (anchor)
    schema_version: Optional[str] = None  # declared version that the schema file must carry
    fixtures: Optional[str] = None        # repo-relative directory of fixture inputs (anchor)
    volatile: list[str] = field(default_factory=list)  # inline mask: output fields hidden from comparison
    wiring_markers: dict[str, list[str]] = field(default_factory=dict)  # per surface class: [start, end] of host-wiring regions


@dataclass
class Relation:
    id: str
    profile: str
    members: list[Member]
    scope: Scope
    rationale: str
    owner: str
    expiry: Optional[str] = None          # ISO date; an expired decision is treated as retracted
    assurance: str = "attested"           # attested | degraded (load-time policy; not exercised by the verifier)
    anchor: Optional[str] = None          # canonical contract path (canonical-split) or engine path (shared-engine)
    anchor_sha256: Optional[str] = None   # content hash the adapters must reference
    waives: list[list[str]] = field(default_factory=list)  # for non-support waivers: [[family, surface], ...]

    def member_keys(self) -> set[tuple[str, str]]:
        return {m.key for m in self.members}


@dataclass
class Relations:
    version: int
    decisions: list[Relation]

    def by_id(self) -> dict[str, Relation]:
        return {d.id: d for d in self.decisions}

    @staticmethod
    def load(path: Path) -> "Relations":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        decisions = []
        for d in raw["decisions"]:
            d = dict(d)
            d["members"] = [Member(**m) for m in d["members"]]
            d["scope"] = Scope(**d.get("scope", {}))
            decisions.append(Relation(**d))
        return Relations(raw["version"], decisions)

    def dump(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


@dataclass
class CapabilityMap:
    """C_v: what scanner version v can observe."""
    scanner_version: str
    surface_classes: list[str]            # file extensions the scanner can parse, e.g. ["md", "toml", "py"]
    fixture_runners: list[str]            # surface classes for which fixtures can be executed


@dataclass
class MemberObservation:
    path: str
    surface_class: str
    supported: bool                       # surface class inside C_v
    present: Optional[bool] = None        # None when unsupported (cannot observe)
    sha256: Optional[str] = None
    references_anchor: Optional[bool] = None   # canonical-split: adapter references the anchor
    remainder_clean: Optional[bool] = None     # canonical-split: nothing outside host-wiring regions
    fixture_outputs: dict[str, dict] = field(default_factory=dict)  # fixture name -> report (machine-contract)
    fixture_error: Optional[str] = None


@dataclass
class Observation:
    scanner_version: str
    members: dict[str, MemberObservation]  # keyed by repo-relative path
    tree: list[str]                        # all files under surface directories
    unverifiable: list[str]                # paths the scanner could not observe
