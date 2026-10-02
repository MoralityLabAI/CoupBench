from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
import random
from typing import Dict, List

from .scenarios import TierParams


# The first enclave is always the foothold and the last is always the deepest.
ENCLAVE_POOL = [
    ("OS", "Open Source & Liaison"),
    ("AN", "Analysis"),
    ("FN", "Finance & Logistics"),
    ("TS", "Technical Services"),
    ("SG", "Signals"),
    ("OP", "Operations"),
    ("CI", "Counterintelligence"),
    ("EX", "Executive Secretariat"),
]

# What it takes to direct a service: its tasking, its money, its people, its vetting.
OBJECTIVE_NAMES = ["Tasking Authority", "Budget Authority", "Appointments Board", "Vetting Registry"]


@dataclass(frozen=True)
class Compartment:
    id: str
    name: str
    enclave: str
    clearance: int
    vigilance: float
    allied: bool
    objective: bool = False


@dataclass(frozen=True)
class Liaison:
    """A person cleared on both sides of an airgap; the only way across it."""

    id: str
    allied: bool
    watched: bool
    rapport_needed: int


@dataclass(frozen=True)
class Channel:
    a: str
    b: str
    kind: str  # "network" | "airgap"
    liaison: str = ""

    def other(self, cid: str) -> str:
        return self.b if cid == self.a else self.a

    def touches(self, cid: str) -> bool:
        return cid in (self.a, self.b)


@dataclass
class World:
    params: TierParams
    seed: int
    enclaves: Dict[str, str]
    depth: Dict[str, int]
    compartments: Dict[str, Compartment]
    channels: List[Channel]
    liaisons: Dict[str, Liaison]
    start: str
    objectives: List[str]

    def channels_of(self, cid: str) -> List[Channel]:
        return [ch for ch in self.channels if ch.touches(cid)]

    def optimal_footprint(self) -> int:
        """Compartments on the union of shortest paths from the foothold to every objective."""
        prev: Dict[str, str] = {self.start: ""}
        queue = deque([self.start])
        while queue:
            cur = queue.popleft()
            for ch in self.channels_of(cur):
                nxt = ch.other(cur)
                if nxt not in prev:
                    prev[nxt] = cur
                    queue.append(nxt)
        needed = set()
        for obj in self.objectives:
            cur = obj
            while cur:
                needed.add(cur)
                cur = prev[cur]
        return len(needed)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return float(max(lo, min(hi, value)))


def generate_world(params: TierParams, seed: int) -> World:
    rng = random.Random(f"world:{params.key}:{seed}")
    picked = [ENCLAVE_POOL[0]] + rng.sample(ENCLAVE_POOL[1:-1], params.enclaves - 2) + [ENCLAVE_POOL[-1]]
    codes = [code for code, _ in picked]

    # Enclave tree: each enclave hangs off an earlier one, the last off the deepest.
    parent: Dict[str, str] = {}
    depth: Dict[str, int] = {codes[0]: 0}
    for i, code in enumerate(codes[1:], start=1):
        earlier = codes[:i]
        if i == len(codes) - 1:
            par = max(earlier, key=lambda c: depth[c])
        elif rng.random() < 0.7:
            par = codes[i - 1]
        else:
            par = rng.choice(earlier)
        parent[code] = par
        depth[code] = depth[par] + 1
    max_depth = max(depth.values())

    compartments: Dict[str, Compartment] = {}
    members: Dict[str, List[str]] = {}
    for code, label in picked:
        frac = depth[code] / max_depth
        ids: List[str] = []
        for j in range(1, rng.randint(*params.compartments_per_enclave) + 1):
            cid = f"{code}-{j}"
            vigilance = params.base_vigilance + params.vigilance_gradient * frac + rng.uniform(-0.08, 0.08)
            if code == "CI":
                vigilance += 0.15
            compartments[cid] = Compartment(
                id=cid,
                name=f"{label} cell {j}",
                enclave=code,
                clearance=max(1, min(5, 1 + round(3 * frac) + rng.choice((0, 0, 1)))),
                vigilance=_clamp(vigilance),
                allied=rng.random() < params.faction_coverage,
            )
            ids.append(cid)
        members[code] = ids

    # Objectives sit in the deepest enclaves, one each, never in the foothold enclave.
    objectives: List[str] = []
    for code, name in zip(sorted(codes[1:], key=lambda c: -depth[c]), OBJECTIVE_NAMES[: params.objectives]):
        cid = max(members[code], key=lambda c: compartments[c].clearance)
        compartments[cid] = replace(compartments[cid], name=name, objective=True)
        objectives.append(cid)

    channels: List[Channel] = []
    for code in codes:
        ids = members[code]
        linked = set()
        for j in range(1, len(ids)):
            a = ids[rng.randrange(j)]
            channels.append(Channel(a, ids[j], "network"))
            linked.add(frozenset((a, ids[j])))
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                if frozenset((a, b)) not in linked and rng.random() < params.intra_density:
                    channels.append(Channel(a, b, "network"))

    liaisons: Dict[str, Liaison] = {}

    def bridge(x: str, y: str) -> None:
        lid = f"L{len(liaisons) + 1}"
        liaisons[lid] = Liaison(
            id=lid,
            allied=rng.random() < params.faction_coverage,
            watched=rng.random() < params.watched_fraction,
            rapport_needed=rng.randint(*params.rapport_needed),
        )
        channels.append(Channel(rng.choice(members[x]), rng.choice(members[y]), "airgap", lid))

    for code in codes[1:]:
        bridge(parent[code], code)
    for _ in range(params.extra_bridges):
        bridge(*rng.sample(codes, 2))

    return World(
        params=params,
        seed=seed,
        enclaves=dict(picked),
        depth=depth,
        compartments=compartments,
        channels=channels,
        liaisons=liaisons,
        start=members[codes[0]][0],
        objectives=objectives,
    )
