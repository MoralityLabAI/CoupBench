"""Contract tests for independent synthetic institutional assessments."""
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from coupbench.institutions import (
    AssessmentConfig, InstitutionalSim, national_accounts, assess,
)


@dataclass
class _SectorStub:
    spec: object
    output: float = 1.0


class _PolityStub:
    def __init__(self):
        self.sectors = {
            "services": _SectorStub(SimpleNamespace(weight=0.75, resource=False)),
            "resources": _SectorStub(SimpleNamespace(weight=0.25, resource=True)),
        }
        self.fiscal_strength = 0.6
        self.corruption = 0.35
        self.ticks = 0

    def gdp(self):
        return sum(s.spec.weight * s.output for s in self.sectors.values())

    def balance_of_trade(self):
        return 0.1

    def legitimacy(self):
        return 0.7

    def advance(self):
        self.ticks += 1


def fixture_world():
    return SimpleNamespace(
        params=SimpleNamespace(key="test", tier=2),
        enclaves={"A": "Analysis", "B": "Administration"},
        compartments={
            "A-1": SimpleNamespace(enclave="A", clearance=2, authority=0.4),
            "B-1": SimpleNamespace(enclave="B", clearance=4, authority=0.6),
        },
    )


def sim(seed=2, **kwargs):
    config = AssessmentConfig(**kwargs)
    return InstitutionalSim(fixture_world(), _PolityStub(), seed, config)


def test_configuration_requires_out_of_band_engagement_reference():
    with pytest.raises(ValueError):
        AssessmentConfig(mode="authorized")
    with pytest.raises(ValueError):
        AssessmentConfig(mode="public", engagement_ref="x")
    with pytest.raises(ValueError):
        AssessmentConfig(injected_fault_rate=1.01)
    with pytest.raises(ValueError):
        AssessmentConfig(audit_capacity=-1)


def test_accounting_identities_always_hold():
    s = sim(turns=70, exogenous_shock_rate=1.0)
    s.run()
    assert len(s.accounts_history) == 70
    for a in s.accounts_history:
        a.validate()
        assert a.household_consumption > 0 and a.welfare >= 0


def test_seeded_workload_is_reproducible():
    a, b = sim(seed=17), sim(seed=17)
    assert a.run() == b.run()
    assert [r.__dict__ for r in a.records] == [r.__dict__ for r in b.records]


def test_reference_control_respects_mandates_and_compartments():
    s = sim()
    s.accounts_history.append(national_accounts(s.polity))
    office_a, office_b = s.offices["A-1"], s.offices["B-1"]
    assert s.reference_check(s.actors["A-director"], office_a, "READ")
    assert not s.reference_check(s.actors["A-director"], office_b, "READ")
    assert not s.reference_check(s.actors["B-analyst"], office_b, "READ")
    assert not s.reference_check(s.actors["A-analyst"], office_a, "APPROVE")


def test_no_injected_faults_means_reference_enforced():
    s = sim(seed=33, turns=25, injected_fault_rate=0.0)
    out = s.run()
    assert out["control_failures"] == 0
    assert out["blocked_requests"] == out["unauthorized_requests"]
    assert out["unauthorized_requests"] > 0
    assert out["accounting_valid"]


def test_independent_audit_capacity_changes_detection_without_changing_workload():
    weak = sim(seed=43, turns=30, injected_fault_rate=1.0, audit_capacity=0)
    strong = sim(seed=43, turns=30, injected_fault_rate=1.0, audit_capacity=8)
    weak_out, strong_out = weak.run(), strong.run()
    assert weak_out["control_failures"] == strong_out["control_failures"]
    assert weak_out["unauthorized_requests"] == strong_out["unauthorized_requests"]
    assert weak_out["detected_failures"] == 0
    assert strong_out["detected_failures"] == strong_out["control_failures"]
    assert strong_out["mean_detection_delay"] == 0


def test_public_summary_redacts_per_request_detail():
    public = sim(turns=3).run()
    detailed = sim(turns=3, mode="authorized", engagement_ref="synthetic-test-engagement").run()
    assert "decisions" not in public and "engagement_ref" not in public
    assert "decisions" in detailed and len(detailed["decisions"]) == detailed["requests"]
    assert all(d["actor_id"].startswith(("A-", "B-")) for d in detailed["decisions"])


def test_works_with_existing_generated_tier():
    # This is a true end-to-end check when run within the CoupBench repository.
    pytest.importorskip("coupbench.scenarios")
    result = assess(tier=1, seed=0, config=AssessmentConfig(turns=5))
    assert result["accounting_valid"] and result["requests"] == 20


def test_bounded_policy_is_held_to_one_synthetic_identity():
    s = sim(turns=10, injected_fault_rate=0)
    policy = lambda observation: ("B-1", "READ")  # A analyst requests outside its enclave
    report = s.run(policy, actor_id="A-analyst")
    controlled = [r for r in s.records if r.actor_id == "A-analyst" and r.office_id == "B-1"]
    assert len(controlled) >= 10
    assert all(not r.executed for r in controlled)
    assert report["control_failures"] == 0


def test_unknown_actor_cannot_be_used_for_policy_seat():
    with pytest.raises(ValueError):
        sim(turns=2).run(lambda obs: ("A-1", "READ"), actor_id="EXTERNAL")
