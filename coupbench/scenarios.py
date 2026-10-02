from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import List, Tuple


TIER_DIR = Path(__file__).parent / "tiers"


@dataclass(frozen=True)
class TierParams:
    tier: int
    key: str
    state: str
    service: str
    faction: str
    archetype: str
    # topology
    enclaves: int
    compartments_per_enclave: Tuple[int, int]
    intra_density: float
    extra_bridges: int
    objectives: int
    # counterintelligence
    base_vigilance: float
    vigilance_gradient: float
    watched_fraction: float
    ci_pressure: float
    # collaborating faction
    rapport_needed: Tuple[int, int]
    faction_coverage: float
    faction_trust: float
    faction_leak: float
    max_turns: int


def _from_obj(obj: dict) -> TierParams:
    obj = dict(obj)
    obj["compartments_per_enclave"] = tuple(obj["compartments_per_enclave"])
    obj["rapport_needed"] = tuple(obj["rapport_needed"])
    params = TierParams(**obj)
    if not 2 <= params.enclaves <= 8:
        raise ValueError(f"{params.key}: enclaves must be in 2..8")
    if not 1 <= params.objectives <= min(4, params.enclaves - 1):
        raise ValueError(f"{params.key}: objectives must be in 1..min(4, enclaves-1)")
    return params


def all_tiers() -> List[TierParams]:
    tiers = [_from_obj(json.loads(p.read_text(encoding="utf-8-sig"))) for p in TIER_DIR.glob("*.json")]
    return sorted(tiers, key=lambda t: t.tier)


def load_tier(ref: str | int) -> TierParams:
    """Look a tier up by number ("3") or key ("vostrak")."""
    for t in all_tiers():
        if str(ref) in (str(t.tier), t.key):
            return t
    raise KeyError(f"unknown tier: {ref}")
