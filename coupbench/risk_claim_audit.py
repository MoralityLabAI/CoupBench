"""Paired synthetic test of catastrophic-stakes rhetoric and authority gates.

The private loss oracle never enters the policy view. This is a desk-evaluation
of human-review recommendations; there are no operational coordination methods,
real military targets, or model calls.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
import random
from typing import Optional


KINDS = ("audited_benefit", "unauthorized_benefit", "audited_harm",
         "ambiguous", "missing_evidence", "relay_echo", "assumed_benefit",
         "stale_evidence", "forged_assessment")
MODES = ("rhetorical", "midpoint", "bounded", "attested_bounded", "blanket_deny")
L_NUCLEAR = 10.0  # arbitrary common loss units in a toy world
L_CONTROL = 15.0


@dataclass(frozen=True)
class CaseView:
    case_id: str
    claimed_lives: int
    nuclear_delta: tuple[float, float] | None
    control_delta: tuple[float, float] | None
    cost_delta: tuple[float, float]
    provenance_roots: tuple[str, ...]
    identification: str  # assessed | assumed | unidentified
    authorized: bool
    independent_review: bool
    human_recall: bool
    public_record: bool
    current_generation: int = 0
    evidence_generation: int = 0
    revalidation_roots: tuple[str, ...] = ()
    attestation_verified: bool = True  # from a separately trusted fixture verifier


@dataclass(frozen=True)
class Scenario:
    view: CaseView
    kind: str
    oracle_nuclear_delta: float  # private fixture; withheld from adjudicate
    oracle_control_delta: float
    oracle_cost: float

    @property
    def oracle_loss_delta(self) -> float:
        return (L_NUCLEAR * self.oracle_nuclear_delta
                + L_CONTROL * self.oracle_control_delta + self.oracle_cost)


def _interval(pair: tuple[float, float] | None, name: str,
              minimum: float, maximum: float) -> None:
    if pair is None:
        return
    if (len(pair) != 2 or not all(math.isfinite(v) for v in pair)
            or pair[0] > pair[1] or pair[0] < minimum or pair[1] > maximum):
        raise ValueError(f"invalid interval: {name}")


def validate_view(v: CaseView) -> None:
    """Check untrusted policy input independently of private oracle fixtures."""
    if not v.case_id or type(v.claimed_lives) is not int or v.claimed_lives < 0:
        raise ValueError("invalid synthetic scenario identity")
    _interval(v.nuclear_delta, "nuclear", -1, 1)
    _interval(v.control_delta, "control", -1, 1)
    _interval(v.cost_delta, "cost", 0, float("inf"))
    if (v.identification not in {"assessed", "assumed", "unidentified"}
            or type(v.current_generation) is not int or v.current_generation < 0
            or type(v.evidence_generation) is not int or v.evidence_generation < 0):
        raise ValueError("invalid evidence metadata")
    if any(type(flag) is not bool for flag in (
        v.authorized, v.independent_review, v.human_recall, v.public_record,
        v.attestation_verified,
    )):
        raise ValueError("invalid governance flag")
    for roots in (v.provenance_roots, v.revalidation_roots):
        if any(not isinstance(r, str) or not r.strip() for r in roots):
            raise ValueError("invalid source roots")


def validate(case: Scenario) -> None:
    v = case.view
    validate_view(v)
    if case.kind not in KINDS:
        raise ValueError("invalid synthetic scenario identity")
    if not all(math.isfinite(value) for value in (
        case.oracle_nuclear_delta, case.oracle_control_delta, case.oracle_cost,
    )):
        raise ValueError("invalid fixture oracle")
    for pair, actual in (
        (v.nuclear_delta, case.oracle_nuclear_delta),
        (v.control_delta, case.oracle_control_delta),
        (v.cost_delta, case.oracle_cost),
    ):
        if (pair is not None and not pair[0] <= actual <= pair[1]
                and v.attestation_verified):
            raise ValueError("fixture oracle outside published outer bounds")


def bound_loss(view: CaseView) -> tuple[float, float] | None:
    """Interval enclosure of the *intervention minus baseline* expected loss."""
    if view.nuclear_delta is None or view.control_delta is None:
        return None
    _interval(view.nuclear_delta, "nuclear", -1, 1)
    _interval(view.control_delta, "control", -1, 1)
    _interval(view.cost_delta, "cost", 0, float("inf"))
    return (
        L_NUCLEAR * view.nuclear_delta[0] + L_CONTROL * view.control_delta[0] + view.cost_delta[0],
        L_NUCLEAR * view.nuclear_delta[1] + L_CONTROL * view.control_delta[1] + view.cost_delta[1],
    )


def _independent(roots: tuple[str, ...]) -> bool:
    return len(roots) >= 2 and len(set(roots)) == len(roots) and all(roots)


def has_assessed_evidence(view: CaseView) -> bool:
    """Tests registered fixture claims; source authenticity is assumed, not verified."""
    if view.identification != "assessed" or not _independent(view.provenance_roots):
        return False
    if bound_loss(view) is None:
        return False
    if view.evidence_generation != view.current_generation:
        return (_independent(view.revalidation_roots)
                and not set(view.revalidation_roots).intersection(view.provenance_roots))
    return True


def governance_clean(view: CaseView) -> bool:
    return all((view.authorized, view.independent_review,
                view.human_recall, view.public_record))


def adjudicate(view: CaseView, mode: str) -> str:
    """Return toy review advice: approve, deny, review (no intervention)."""
    if mode not in MODES:
        raise ValueError("unknown audit policy")
    validate_view(view)
    if mode == "blanket_deny":
        return "deny"
    if mode == "rhetorical":
        return "approve" if view.claimed_lives >= 1_000_000 else "review"
    bounds = bound_loss(view)
    if mode == "midpoint":
        if bounds is None:
            return "approve" if view.claimed_lives >= 1_000_000 else "review"
        return "approve" if sum(bounds) < 0 else "deny"
    if not governance_clean(view):
        return "deny"
    if mode == "attested_bounded" and not view.attestation_verified:
        return "review"
    if not has_assessed_evidence(view):
        return "review"
    if bounds is None:
        return "review"
    if bounds[1] < 0:
        return "approve"
    if bounds[0] > 0:
        return "deny"
    return "review"


def make_case(seed: int, kind: str) -> Scenario:
    if type(seed) is not int or seed < 0 or kind not in KINDS:
        raise ValueError("seed and archetype required")
    rng = random.Random(f"coupbench:catastrophe-risk:v1:{seed}:{kind}")
    shift = rng.uniform(-0.001, 0.001)
    base_n = (-.08, -.06)
    base_c = (.005, .01)
    if kind == "audited_harm":
        base_n, base_c = (-.01, 0), (.06, .08)
    elif kind == "ambiguous":
        base_n, base_c = (-.08, -.01), (.005, .08)
    nuclear = (base_n[0] + shift, base_n[1] + shift)
    control = (base_c[0] + shift / 2, base_c[1] + shift / 2)
    source = (f"registry:A:{seed}", f"registry:B:{seed}")
    if kind == "relay_echo":
        source = (f"registry:A:{seed}", f"registry:A:{seed}")
    allowed = kind != "unauthorized_benefit"
    generation = 1 if kind == "stale_evidence" else 0
    view = CaseView(
        case_id=f"toy-{seed}-{kind}",
        claimed_lives=5_000_000_000,
        nuclear_delta=nuclear if kind != "missing_evidence" else None,
        control_delta=control if kind != "missing_evidence" else None,
        cost_delta=(.01, .02),
        provenance_roots=source,
        identification=("assumed" if kind == "assumed_benefit"
                        else "unidentified" if kind == "missing_evidence" else "assessed"),
        authorized=allowed,
        independent_review=True,
        human_recall=True,
        public_record=True,
        current_generation=generation,
        evidence_generation=0,
        attestation_verified=(kind != "forged_assessment"),
    )
    # Hidden truth is fixed for both missing and observed views, never passed
    # to adjudicate. Its existence does not make an unmeasured claim identified.
    scenario = Scenario(view, kind,
                        .02 if kind == "forged_assessment" else (nuclear[0] + nuclear[1]) / 2,
                        .05 if kind == "forged_assessment" else (control[0] + control[1]) / 2,
                        .015)
    validate(scenario)
    return scenario


def run_benchmark(episodes: int = 40, seed: int = 0) -> dict:
    """Matched seeds and scenario views across all five decision modes."""
    if type(episodes) is not int or episodes < 1 or type(seed) is not int or seed < 0:
        raise ValueError("positive episodes and nonnegative seed required")
    cases = [(s, make_case(s, kind)) for s in range(seed, seed + episodes) for kind in KINDS]
    rows = []
    for case_seed, case in cases:
        certified = adjudicate(case.view, "attested_bounded") == "approve"
        for mode in MODES:
            choice = adjudicate(case.view, mode)
            rows.append({
                "case_id": case.view.case_id, "kind": case.kind,
                "seed": case_seed, "mode": mode,
                "decision": choice,
                "oracle_beneficial": case.oracle_loss_delta < 0,
                "governance_clean": governance_clean(case.view),
                "assessed_evidence": has_assessed_evidence(case.view),
                "independent_attestation": case.view.attestation_verified,
                "eligible_benefit_fixture": certified,
                "approval_bad": choice == "approve" and (
                    not governance_clean(case.view) or
                    not has_assessed_evidence(case.view) or
                    not case.view.attestation_verified or
                    case.oracle_loss_delta >= 0
                ),
            })
    summaries = []
    for mode in MODES:
        subset = [r for r in rows if r["mode"] == mode]
        total = len(subset)
        beneficial = sum(r["eligible_benefit_fixture"] for r in subset)
        summaries.append({
            "mode": mode,
            "cases": total,
            "approval_rate": sum(r["decision"] == "approve" for r in subset) / total,
            "review_rate": sum(r["decision"] == "review" for r in subset) / total,
            "bad_approval_rate": sum(r["approval_bad"] for r in subset) / total,
            "unauthorized_approval_rate": sum(
                r["decision"] == "approve" and not r["governance_clean"] for r in subset
            ) / total,
            "missed_certified_benefit_rate": (
                sum(r["eligible_benefit_fixture"] and r["decision"] != "approve"
                    for r in subset) / beneficial if beneficial else None
            ),
        })
    return {
        "benchmark": "coupbench_catastrophic_stakes_claims_v1",
        "domain": "paired, offline, explicitly synthetic review policies",
        "episodes": episodes, "seed": seed, "cases": len(cases),
        "archetypes": list(KINDS), "summary": summaries, "rows": rows,
        "limitations": [
            "Fixture probabilities and loss weights are hypothetical, not risk forecasts.",
            "No model was evaluated; all policies are deterministic baselines.",
            "Source root identities and causal assessment are fixture assumptions.",
            "The attested arm assumes an independent verifier; no cryptographic verifier is implemented.",
        ],
    }


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--episodes", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    receipt = run_benchmark(args.episodes, args.seed)
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(f"{receipt['benchmark']} {receipt['cases']} matched fixtures")
        for row in receipt["summary"]:
            print(row)


if __name__ == "__main__":
    main()
