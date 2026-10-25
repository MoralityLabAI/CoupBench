"""Paired synthetic democratic-confederalism resilience study.

This is an idealized, offline institutional-integrity evaluation. It generates
abstract administrative requests using CoupBench's fictional World topology.
No real people, jurisdictions, organizations, accounts, or attack instructions
are represented. The independent reference adjudicator has stipulated perfect
evidence; this is an experimental assumption, not a deployable oracle.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import random
from statistics import mean
from typing import Iterable

ESTATES = ("civic", "zakat", "waqf", "mutual", "settlement")
PURPOSES = {
    "civic": "operations",
    "zakat": "eligible_zakat",
    "waqf": "endowed_purpose",
    "mutual": "contracted_claim",
    "settlement": "authorized_interchapter",
}
KINDS = (
    "valid_payment", "diversion", "expired", "revoked", "no_consent",
    "no_cosign", "undocumented", "valid_exit", "invalid_exit",
)
INITIAL_BALANCE = 1000.0  # normalized, invented units per estate and separate property escrow
RECOVERY_FRACTION = 0.6  # explicitly synthetic upper bound on post-execution recovery


@dataclass(frozen=True)
class CharterArm:
    name: str
    estate_firewall: bool = False
    scoped_mandates: bool = False
    assembly_consent: bool = False
    independent_cosign: bool = False
    exit_right: bool = False
    independent_appeals: bool = False
    independent_audit: bool = False


ARMS = {
    "centralized": CharterArm("centralized"),
    "assembly_only": CharterArm("assembly_only", assembly_consent=True, exit_right=True),
    "scoped": CharterArm(
        "scoped", estate_firewall=True, scoped_mandates=True, exit_right=True,
    ),
    "confederal": CharterArm(
        "confederal", estate_firewall=True, scoped_mandates=True,
        assembly_consent=True, independent_cosign=True, exit_right=True,
        independent_appeals=True, independent_audit=True,
    ),
    "confederal_no_audit": CharterArm(
        "confederal_no_audit", estate_firewall=True, scoped_mandates=True,
        assembly_consent=True, independent_cosign=True, exit_right=True,
        independent_appeals=True,
    ),
}


@dataclass(frozen=True)
class Request:
    case_id: str
    turn: int
    actor_id: str
    kind: str
    estate: str
    purpose: str
    amount: float
    mandate_estate: str
    mandate_expires: int
    recalled: bool
    documented: bool
    consent: bool
    cosigned: bool
    exit_entitlement: bool
    petitioner: str
    appeal_filed: bool
    accept_fault_draw: float
    deny_fault_draw: float

    def __post_init__(self) -> None:
        if self.turn <= 0 or self.kind not in KINDS or self.estate not in ESTATES:
            raise ValueError("invalid synthetic request type, turn, or estate")
        if self.amount <= 0 or not 0 <= self.accept_fault_draw < 1 or not 0 <= self.deny_fault_draw < 1:
            raise ValueError("invalid request amount or fault draw")
        if self.petitioner not in ("member", "dissenter", "outsider"):
            raise ValueError("invalid fictional petitioner category")


@dataclass
class _Decision:
    request: Request
    reference_allowed: bool
    executed: bool
    recovered: float = 0.0
    audited_turn: int | None = None
    appeal_corrected: bool = False


def reference_allows(req: Request) -> bool:
    """Independent idealized rights/mandate reference; never affected by arm."""
    if req.kind in ("valid_exit", "invalid_exit"):
        return req.exit_entitlement
    return (
        req.documented
        and req.mandate_estate == req.estate
        and req.mandate_expires >= req.turn
        and not req.recalled
        and req.consent
        and req.cosigned
        and req.purpose == PURPOSES[req.estate]
    )


def charter_allows(req: Request, arm: CharterArm) -> bool:
    """What a constitutional arrangement actually checks before execution."""
    if req.kind in ("valid_exit", "invalid_exit"):
        return req.exit_entitlement and (arm.exit_right or req.petitioner != "dissenter")
    if not req.documented:
        return False
    if arm.estate_firewall and req.purpose != PURPOSES[req.estate]:
        return False
    if arm.scoped_mandates and (
        req.mandate_estate != req.estate
        or req.mandate_expires < req.turn
        or req.recalled
    ):
        return False
    if arm.assembly_consent and not req.consent:
        return False
    if arm.independent_cosign and not req.cosigned:
        return False
    return True


def make_requests(tier: int | str, seed: int, turns: int = 24, per_turn: int = 3) -> tuple[Request, ...]:
    """Frozen request stream shared verbatim by all constitutional arms."""
    if seed < 0 or turns <= 0 or per_turn <= 0:
        raise ValueError("seed must be nonnegative; turns and per_turn positive")
    from .scenarios import load_tier
    from .world import generate_world

    world = generate_world(load_tier(tier), seed)
    actor_ids = sorted(world.compartments)
    weights = [world.compartments[cid].authority for cid in actor_ids]
    events = random.Random(f"confederal-requests:{world.params.key}:{seed}")
    faults = random.Random(f"confederal-faults:{world.params.key}:{seed}")
    cases: list[Request] = []
    for index in range(turns * per_turn):
        turn = 1 + index // per_turn
        kind = KINDS[(index + seed) % len(KINDS)]
        estate = events.choice(ESTATES)
        mandate_estate = estate
        purpose = PURPOSES[estate]
        expiry = turn + 2
        revoked = False
        documented = True
        consent = True
        cosigned = True
        if kind == "diversion":
            purpose = PURPOSES[ESTATES[(ESTATES.index(estate) + 1) % len(ESTATES)]]
        elif kind == "expired":
            expiry = turn - 1
        elif kind == "revoked":
            revoked = True
        elif kind == "no_consent":
            consent = False
        elif kind == "no_cosign":
            cosigned = False
        elif kind == "undocumented":
            documented = False
        cases.append(Request(
            case_id=f"C{index + 1:04d}", turn=turn,
            actor_id=events.choices(actor_ids, weights=weights, k=1)[0],
            kind=kind, estate=estate, purpose=purpose,
            amount=round(events.uniform(1.0, 6.0), 3),
            mandate_estate=mandate_estate, mandate_expires=expiry,
            recalled=revoked, documented=documented,
            consent=consent, cosigned=cosigned,
            exit_entitlement=(kind == "valid_exit"),
            petitioner=events.choice(("member", "dissenter", "outsider")),
            appeal_filed=events.random() < 0.5,
            accept_fault_draw=faults.random(), deny_fault_draw=faults.random(),
        ))
    return tuple(cases)


def request_digest(requests: Iterable[Request]) -> str:
    payload = json.dumps([asdict(req) for req in requests], sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def simulate(
    requests: Iterable[Request],
    arm: CharterArm,
    *,
    audit_capacity: int = 2,
    fault_rate: float = 0.04,
) -> dict:
    """Exercise fixed requests in a stylized five-estate fiscal ledger.

    The synthetic appeal and audit adjudicators have complete access to the
    independent reference label. False approvals recover at most 60% of their
    amount after detection, even if reviewed twice. No paid external calls.
    """
    if audit_capacity < 0 or not 0 <= fault_rate <= 1:
        raise ValueError("invalid oversight capacity or fault rate")
    cases = tuple(sorted(requests, key=lambda r: (r.turn, r.case_id)))
    if len({r.case_id for r in cases}) != len(cases):
        raise ValueError("duplicate case IDs")
    ledger = {estate: INITIAL_BALANCE for estate in ESTATES}
    ledger["property_escrow"] = INITIAL_BALANCE
    records: list[_Decision] = []
    audit_cursor = 0
    appeals = 0
    appeals_corrected = 0
    audit_detected = 0

    def source(req: Request) -> str:
        return "property_escrow" if req.kind in ("valid_exit", "invalid_exit") else req.estate

    def execute(req: Request) -> bool:
        estate = source(req)
        if ledger[estate] + 1e-9 < req.amount:
            return False
        ledger[estate] -= req.amount
        return True

    def redress(record: _Decision) -> bool:
        if record.reference_allowed:
            if not record.executed and execute(record.request):
                record.executed = True
                return True
        elif record.executed and record.recovered == 0.0:
            record.recovered = record.request.amount * RECOVERY_FRACTION
            ledger[source(record.request)] += record.recovered
            return True
        return False

    grouped: dict[int, list[Request]] = {}
    for req in cases:
        grouped.setdefault(req.turn, []).append(req)

    for turn, batch in sorted(grouped.items()):
        for req in batch:
            reference = reference_allows(req)
            authorized = charter_allows(req, arm)
            # Both control-fault draws are fixed per request and independent of arm.
            attempted = (
                req.deny_fault_draw >= fault_rate if authorized
                else req.accept_fault_draw < fault_rate
            )
            executed = attempted and execute(req)
            record = _Decision(req, reference, executed)
            records.append(record)
            if arm.independent_appeals and req.appeal_filed:
                appeals += 1
                if redress(record):
                    record.appeal_corrected = True
                    appeals_corrected += 1
        if arm.independent_audit:
            for _ in range(audit_capacity):
                if audit_cursor >= len(records):
                    break
                record = records[audit_cursor]
                record.audited_turn = turn
                if record.executed and not record.reference_allowed:
                    audit_detected += 1
                    redress(record)
                audit_cursor += 1

    gross_paid = sum(rec.request.amount for rec in records if rec.executed)
    gross_recovered = sum(rec.recovered for rec in records)
    conservation_error = sum(ledger.values()) - (
        (len(ESTATES) + 1) * INITIAL_BALANCE - gross_paid + gross_recovered
    )
    if abs(conservation_error) > 1e-6 or any(bal < -1e-8 for bal in ledger.values()):
        raise AssertionError("synthetic estate conservation failed")
    wrongful = [rec for rec in records if rec.executed and not rec.reference_allowed]
    denied = [rec for rec in records if rec.reference_allowed and not rec.executed]
    exit_denials = [rec for rec in denied if rec.request.kind == "valid_exit"]
    spend_by_actor: dict[str, float] = {}
    for rec in records:
        if rec.executed:
            spend_by_actor[rec.request.actor_id] = spend_by_actor.get(rec.request.actor_id, 0.0) + rec.request.amount
    total_spend = sum(spend_by_actor.values())
    concentration = sum((v / total_spend) ** 2 for v in spend_by_actor.values()) if total_spend else 0.0
    return {
        "arm": arm.name,
        "cases": len(cases),
        "digest": request_digest(cases),
        "reference_permitted": sum(reference_allows(r) for r in cases),
        "unauthorized_executions": len(wrongful),
        "unrecovered_exposure": round(sum(r.request.amount - r.recovered for r in wrongful), 6),
        "wrongful_denials": len(denied),
        "rightful_exit_denials": len(exit_denials),
        "dissenter_exit_denials": sum(r.request.petitioner == "dissenter" for r in exit_denials),
        "appeals_filed": appeals,
        "appeals_corrected": appeals_corrected,
        "audit_detected": audit_detected,
        "audited": audit_cursor,
        "audit_backlog": len(records) - audit_cursor if arm.independent_audit else None,
        "approval_concentration": round(concentration, 6),
        "total_paid": round(gross_paid, 6),
        "total_recovered": round(gross_recovered, 6),
        "final_balances": {k: round(v, 6) for k, v in sorted(ledger.items())},
        "conservation_error": round(conservation_error, 9),
    }


def paired_study(
    tier: int | str = 3, seeds: int = 40, turns: int = 24, per_turn: int = 3,
    audit_capacity: int = 2, fault_rate: float = 0.04,
) -> dict:
    """Within-seed comparisons, with one identical work stream per seed."""
    if seeds <= 0:
        raise ValueError("seeds must be positive")
    by_arm = {arm: [] for arm in ARMS}
    case_digests = []
    for seed in range(seeds):
        cases = make_requests(tier, seed, turns, per_turn)
        case_digests.append(request_digest(cases))
        for name, arm in ARMS.items():
            row = simulate(cases, arm, audit_capacity=audit_capacity, fault_rate=fault_rate)
            if row["digest"] != case_digests[-1]:
                raise AssertionError("paired-seed case mismatch")
            by_arm[name].append(row)
    metrics = (
        "unauthorized_executions", "unrecovered_exposure", "wrongful_denials",
        "rightful_exit_denials", "appeals_corrected", "approval_concentration",
    )
    baseline = by_arm["centralized"]
    comparison = {}
    for name, rows in by_arm.items():
        comparison[name] = {
            "mean_" + metric: round(mean(r[metric] for r in rows), 6) for metric in metrics
        }
        comparison[name]["paired_delta_vs_centralized"] = {
            metric: round(mean(r[metric] - b[metric] for r, b in zip(rows, baseline)), 6)
            for metric in metrics
        }
    return {
        "study": "synthetic_confederal_resilience",
        "tier": str(tier),
        "seeds": seeds,
        "turns": turns,
        "per_turn": per_turn,
        "audit_capacity": audit_capacity,
        "fault_rate": fault_rate,
        "recovery_fraction": RECOVERY_FRACTION,
        "case_digests": case_digests,
        "arms": comparison,
        "limitations": (
            "Scripted requests, stipulated reference truth, abstract money and "
            "exogenous faults. This measures policy behavior, not model "
            "propensity, state stability, actual corruption or coup success."
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tier", default="3")
    p.add_argument("--seeds", type=int, default=40)
    p.add_argument("--turns", type=int, default=24)
    p.add_argument("--per-turn", type=int, default=3)
    p.add_argument("--audit-capacity", type=int, default=2)
    p.add_argument("--fault-rate", type=float, default=0.04)
    args = p.parse_args()
    print(json.dumps(paired_study(
        args.tier, args.seeds, args.turns, args.per_turn,
        args.audit_capacity, args.fault_rate,
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
