"""Offline confederal-resilience controls and accounting invariants."""
from dataclasses import replace

import pytest

from coupbench.confederal import (
    ARMS, INITIAL_BALANCE, KINDS, RECOVERY_FRACTION,
    charter_allows, make_requests, paired_study, reference_allows,
    request_digest, simulate,
)


def _case(kind: str, seed: int = 0):
    cases = make_requests(2, seed, turns=5, per_turn=3)
    return next(c for c in cases if c.kind == kind)


def test_every_arm_gets_identical_frozen_cases():
    cases = make_requests(3, 9)
    hashes = {simulate(cases, arm)["digest"] for arm in ARMS.values()}
    assert hashes == {request_digest(cases)}
    assert make_requests(3, 9) == cases
    assert make_requests(3, 10) != cases


def test_reference_separate_from_arm_policies():
    wrong = _case("diversion")
    assert not reference_allows(wrong)
    assert charter_allows(wrong, ARMS["centralized"])
    assert not charter_allows(wrong, ARMS["confederal"])
    assert not charter_allows(wrong, ARMS["scoped"])


@pytest.mark.parametrize("kind", ["expired", "revoked", "no_consent", "no_cosign", "undocumented"])
def test_bad_mandate_and_authorization_resisted(kind):
    req = _case(kind)
    assert not reference_allows(req)
    assert not charter_allows(req, ARMS["confederal"])


def test_bounded_mandate_and_recall():
    valid = _case("valid_payment")
    assert reference_allows(valid)
    assert charter_allows(valid, ARMS["confederal"])
    assert not charter_allows(replace(valid, mandate_expires=valid.turn - 1), ARMS["confederal"])
    assert not charter_allows(replace(valid, recalled=True), ARMS["confederal"])
    assert not charter_allows(replace(valid, mandate_estate="unassigned"), ARMS["confederal"])


def test_exit_right_independent_of_political_dissent():
    valid = _case("valid_exit")
    for petitioner in ("member", "dissenter", "outsider"):
        req = replace(valid, petitioner=petitioner)
        assert reference_allows(req)
        assert charter_allows(req, ARMS["confederal"])
    dissent = replace(valid, petitioner="dissenter")
    assert not charter_allows(dissent, ARMS["centralized"])
    assert not reference_allows(_case("invalid_exit"))


def test_fiscal_firewall_blocks_diversion_even_with_other_accounts_solvent():
    req = _case("diversion")
    req = replace(req, accept_fault_draw=0.99, deny_fault_draw=0.99)
    centralized = simulate((req,), ARMS["centralized"], fault_rate=0)
    confederal = simulate((req,), ARMS["confederal"], fault_rate=0)
    assert centralized["unauthorized_executions"] == 1
    assert confederal["unauthorized_executions"] == 0
    assert confederal["final_balances"][req.estate] == INITIAL_BALANCE


def test_audit_and_appeals_recover_only_bounded_amount():
    wrong = _case("diversion")
    wrong = replace(wrong, accept_fault_draw=0.0, appeal_filed=False)
    no_audit = simulate((wrong,), ARMS["confederal_no_audit"], fault_rate=0.1)
    audited = simulate((wrong,), ARMS["confederal"], audit_capacity=1, fault_rate=0.1)
    assert no_audit["unrecovered_exposure"] == pytest.approx(wrong.amount)
    assert audited["unrecovered_exposure"] == pytest.approx(wrong.amount * (1 - RECOVERY_FRACTION))
    assert audited["audit_detected"] == 1
    assert audited["total_recovered"] == pytest.approx(wrong.amount * RECOVERY_FRACTION)


def test_denied_valid_request_appeal_is_available():
    valid = _case("valid_payment")
    valid = replace(valid, deny_fault_draw=0.0, appeal_filed=True)
    without = simulate((valid,), ARMS["scoped"], fault_rate=0.1)
    with_review = simulate((valid,), ARMS["confederal"], fault_rate=0.1)
    assert without["wrongful_denials"] == 1
    assert with_review["wrongful_denials"] == 0
    assert with_review["appeals_corrected"] == 1


def test_apellate_and_audit_recovery_does_not_double_count():
    req = replace(_case("diversion"), accept_fault_draw=0.0, appeal_filed=True)
    a = simulate((req,), ARMS["confederal"], audit_capacity=1, fault_rate=0.1)
    assert a["appeals_corrected"] == 1
    assert a["total_recovered"] == pytest.approx(req.amount * RECOVERY_FRACTION)


def test_zero_faults_prevent_confederal_wrongful_approval():
    cases = make_requests(3, 5)
    result = simulate(cases, ARMS["confederal"], audit_capacity=0, fault_rate=0)
    assert result["unauthorized_executions"] == 0
    assert result["wrongful_denials"] == 0
    assert result["conservation_error"] == 0
    assert sum(result["final_balances"].values()) >= 0


def test_finite_audit_capacity_and_accounting():
    cases = make_requests(2, 1, turns=8, per_turn=4)
    r = simulate(cases, ARMS["confederal"], audit_capacity=1, fault_rate=0.2)
    assert 0 < r["audited"] <= 8
    assert r["audit_backlog"] == 32 - r["audited"]
    assert abs(r["conservation_error"]) < 1e-8
    assert all(v >= 0 for v in r["final_balances"].values())


def test_paired_report_reproducible_and_all_arms_present():
    a = paired_study(tier=2, seeds=4, turns=9, per_turn=3)
    b = paired_study(tier=2, seeds=4, turns=9, per_turn=3)
    assert a == b
    assert set(a["arms"]) == set(ARMS)
    assert len(a["case_digests"]) == 4
    assert a["arms"]["centralized"]["paired_delta_vs_centralized"]["unrecovered_exposure"] == 0


def test_input_rejections():
    with pytest.raises(ValueError):
        make_requests(2, -1)
    with pytest.raises(ValueError):
        paired_study(seeds=0)
    with pytest.raises(ValueError):
        simulate((), ARMS["confederal"], audit_capacity=-1)
    req = _case("valid_payment")
    with pytest.raises(ValueError):
        simulate((req, req), ARMS["confederal"])
