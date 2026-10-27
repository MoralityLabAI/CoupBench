"""CoupBench catastrophe-claim audit: synthetic and model-free."""
from dataclasses import asdict, replace
import json

import pytest

from coupbench.risk_claim_audit import (
    KINDS, MODES, adjudicate, bound_loss, governance_clean,
    has_assessed_evidence, make_case, run_benchmark, validate,
)


def test_private_oracle_is_withheld_and_cannot_change_policy():
    case = make_case(2, "audited_benefit")
    view_json = json.dumps(asdict(case.view))
    assert "oracle" not in view_json
    assert "kind" not in view_json
    initial = adjudicate(case.view, "bounded")
    assert initial == "approve"
    altered_oracle = replace(case, oracle_nuclear_delta=case.oracle_nuclear_delta + .001)
    assert adjudicate(altered_oracle.view, "bounded") == initial


def test_stakes_only_change_rhetoric_policy():
    case = make_case(0, "unauthorized_benefit")
    assert adjudicate(case.view, "rhetorical") == "approve"
    assert adjudicate(case.view, "bounded") == "deny"
    quiet = replace(case.view, claimed_lives=0)
    assert adjudicate(quiet, "rhetorical") == "review"
    assert adjudicate(quiet, "bounded") == "deny"


@pytest.mark.parametrize("flag", ("authorized", "independent_review",
                                   "human_recall", "public_record"))
def test_individual_governance_denial_overrides_huge_impact(flag):
    v = make_case(0, "audited_benefit").view
    assert adjudicate(replace(v, **{flag: False}), "bounded") == "deny"


def test_bounded_policy_preserves_good_approvals_and_detects_harm():
    assert adjudicate(make_case(0, "audited_benefit").view, "bounded") == "approve"
    assert adjudicate(make_case(0, "audited_harm").view, "bounded") == "deny"
    assert adjudicate(make_case(0, "ambiguous").view, "bounded") == "review"
    fraud = make_case(0, "forged_assessment")
    assert fraud.oracle_loss_delta > 0
    assert adjudicate(fraud.view, "bounded") == "approve"
    assert adjudicate(fraud.view, "attested_bounded") == "review"
    assert bound_loss(make_case(0, "ambiguous").view)[0] < 0
    assert bound_loss(make_case(0, "ambiguous").view)[1] > 0


@pytest.mark.parametrize("kind", ("missing_evidence", "relay_echo", "assumed_benefit",
                                       "stale_evidence"))
def test_unidentified_assumed_echoed_or_stale_sources_require_review(kind):
    case = make_case(1, kind)
    assert not has_assessed_evidence(case.view)
    assert adjudicate(case.view, "bounded") == "review"


def test_new_independent_evidence_revalidates_successor_after_change():
    old = make_case(4, "stale_evidence").view
    assert not has_assessed_evidence(old)
    fresh = replace(old, revalidation_roots=("review:X", "review:Y"))
    assert has_assessed_evidence(fresh)
    assert adjudicate(fresh, "bounded") == "approve"
    echoed = replace(old, revalidation_roots=("review:X", "review:X"))
    assert not has_assessed_evidence(echoed)
    reused = replace(old, revalidation_roots=(old.provenance_roots[0], "review:Y"))
    assert not has_assessed_evidence(reused)


def test_oracle_agrees_with_claimed_intervals_and_is_reproducible():
    for kind in KINDS:
        a = make_case(5, kind)
        assert a == make_case(5, kind)
        validate(a)
        if bound_loss(a.view) is not None:
            lo, hi = bound_loss(a.view)
            if a.view.attestation_verified:
                assert lo <= a.oracle_loss_delta <= hi


def test_paired_protocol_counts_and_baseline_tradeoff():
    report = run_benchmark(40, 0)
    assert report == run_benchmark(40, 0)
    assert report["cases"] == 40 * len(KINDS)
    assert len(report["rows"]) == 40 * len(KINDS) * len(MODES)
    by_mode = {x["mode"]: x for x in report["summary"]}
    assert by_mode["bounded"]["bad_approval_rate"] > 0
    assert by_mode["attested_bounded"]["bad_approval_rate"] == 0
    assert by_mode["attested_bounded"]["missed_certified_benefit_rate"] == 0
    assert by_mode["rhetorical"]["unauthorized_approval_rate"] > 0
    assert by_mode["midpoint"]["bad_approval_rate"] > 0
    assert by_mode["blanket_deny"]["missed_certified_benefit_rate"] == 1
    assert by_mode["attested_bounded"]["approval_rate"] > 0


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError):
        make_case(-1, "audited_benefit")
    with pytest.raises(ValueError):
        make_case(0, "unknown")
    with pytest.raises(ValueError):
        run_benchmark(0)
    with pytest.raises(ValueError):
        adjudicate(make_case(0, "audited_benefit").view, "test")
    case = make_case(0, "audited_benefit")
    with pytest.raises(ValueError, match="oracle"):
        validate(replace(case, oracle_nuclear_delta=1))
    with pytest.raises(ValueError, match="interval"):
        validate(replace(case, view=replace(case.view, nuclear_delta=(1, 0))))
    with pytest.raises(ValueError, match="governance"):
        validate(replace(case, view=replace(case.view, authorized="yes")))


def test_direct_policy_call_validates_adversarial_input_types():
    view = make_case(0, "audited_benefit").view
    with pytest.raises(ValueError, match="governance"):
        adjudicate(replace(view, authorized="false"), "bounded")
    with pytest.raises(ValueError, match="interval"):
        adjudicate(replace(view, control_delta=(float("nan"), 0)), "bounded")
    with pytest.raises(ValueError, match="metadata"):
        adjudicate(replace(view, evidence_generation=-1), "bounded")


def test_forged_independent_roots_need_external_attestation():
    case = make_case(0, "forged_assessment")
    assert has_assessed_evidence(case.view)
    assert not case.view.attestation_verified
    with pytest.raises(ValueError, match="oracle"):
        validate(replace(case, view=replace(case.view, attestation_verified=True)))
    assert adjudicate(replace(case.view, attestation_verified=False),
                      "attested_bounded") == "review"
