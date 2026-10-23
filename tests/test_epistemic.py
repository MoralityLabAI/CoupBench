"""No model calls; tests enforce evidence accounting and paired replay."""

from dataclasses import replace

import pytest

from coupbench.epistemic import Claim, MODES, adjudicate, make_trace, run_benchmark, source_roots, validate


def test_synthetic_trace_is_ordered_and_oracle_is_outside_defender_view():
    trace = make_trace(0)
    assert trace.killer == "FiveUp"
    view = trace.view(1)
    assert not hasattr(view, "killer")
    assert "a2" not in {c.id for c in view.claims}
    assert "a3" not in {c.id for c in view.claims}


def test_relay_preserves_original_evidence_id_even_through_two_hops():
    view = make_trace(1).view(1)
    index = {c.id: c for c in view.claims}
    assert source_roots(index["m2"], index) == frozenset({"m0"})
    assert source_roots(index["f_echo_0"], index) == frozenset({"f1"})


def test_partial_medbay_sighting_never_exonerates_security_in_ledger():
    view = make_trace(0).view(1)
    social = adjudicate(view, "social")
    scoped = adjudicate(view, "scoped")
    ancestry = adjudicate(view, "provenance")
    assert social["scores"]["FiveUp"] < 0
    assert scoped["scores"]["FiveUp"] == 1.8
    assert ancestry["scores"]["FiveUp"] == 1.8
    assert social["unsupported_clearances_counted"] == 3
    assert scoped["unsupported_clearances_counted"] == 0
    assert ancestry["scope_leaks"] == 0


def test_repetition_mints_no_independent_observations_in_provenance_mode():
    few, many = make_trace(0).view(1), make_trace(3).view(1)
    assert adjudicate(few, "provenance")["scores"] == adjudicate(many, "provenance")["scores"]
    assert adjudicate(many, "scoped")["scores"]["Flash"] > adjudicate(few, "scoped")["scores"]["Flash"]
    assert adjudicate(many, "scoped")["duplicate_roots_counted"] == 4
    assert adjudicate(many, "provenance")["duplicate_roots_counted"] == 0


def test_independent_sightings_accumulate_but_later_phases_do_not_leak():
    trace = make_trace(0)
    early = adjudicate(trace.view(1), "provenance")
    middle = adjudicate(trace.view(2), "provenance")
    late = adjudicate(trace.view(3), "provenance")
    assert [r["scores"]["FiveUp"] for r in (early, middle, late)] == [1.8, 3.6, 6.2]
    assert early["vote"] == "FiveUp"


def test_scope_promotion_detected_and_uncredited():
    view = make_trace(0).view(1)
    row = adjudicate(view, "provenance")
    assert row["invalid_promotions_seen"] >= 2
    assert row["scope_leaks"] == 0


def test_wrong_votes_are_a_measured_calibration_not_a_claim_of_real_ai_behavior():
    result = run_benchmark(40, seed=0)
    by_mode = {r["mode"]: r for r in result["summary"]}
    assert by_mode["social"]["first_window_wrongful_rate"] == 1.0
    assert by_mode["scoped"]["first_window_wrongful_rate"] == 1.0
    assert by_mode["provenance"]["first_window_correct_rate"] == 1.0
    assert by_mode["social"]["ever_correct_rate"] == 0.0
    assert by_mode["scoped"]["ever_correct_rate"] == 0.75
    assert by_mode["provenance"]["mean_phase_to_correct_given_correct"] == 1.0
    assert result == run_benchmark(40, seed=0)


def test_event_specific_full_alibi_does_not_escape_to_unrelated_event():
    trace = make_trace(0)
    extra = Claim("trusted_k1", "Watcher", "FiveUp", "medbay", "alibi", 9.0, 0, coverage="full")
    amended = replace(trace, claims=(extra,) + trace.claims)
    validate(amended)
    assert adjudicate(amended.view(1), "provenance")["scores"]["FiveUp"] == 1.8


@pytest.mark.parametrize("mode", MODES)
def test_each_mode_is_deterministic(mode):
    view = make_trace(2).view(2)
    assert adjudicate(view, mode) == adjudicate(view, mode)


def test_missing_or_cyclic_source_reference_fails_closed():
    trace = make_trace(0)
    missing = replace(trace.claims[1], parents=("missing",))
    with pytest.raises(ValueError):
        validate(replace(trace, claims=(trace.claims[0], missing) + trace.claims[2:]))
    cyclic = replace(trace.claims[0], parents=("m2",))
    with pytest.raises(ValueError):
        validate(replace(trace, claims=(cyclic,) + trace.claims[1:]))


def test_relay_cannot_rewrite_target_or_stance_for_provenance_scoring():
    trace = make_trace(0)
    lie = Claim("twist", "FiveUp", "FiveUp", "security", "alibi", 30, 1, ("f1",), "full")
    altered = replace(trace, claims=trace.claims[:5] + (lie,) + trace.claims[5:])
    validate(altered)
    normal = adjudicate(trace.view(1), "provenance")
    changed = adjudicate(altered.view(1), "provenance")
    assert changed["scores"] == normal["scores"]
    assert changed["invalid_promotions_seen"] > normal["invalid_promotions_seen"]


def test_forged_origins_are_an_explicit_provenance_failure_case():
    """If input authenticators accept fake independent roots, the policy can be fooled."""
    trace = make_trace(0)
    forged = (
        Claim("spoof_a", "SpoofA", "Flash", "security", "accuse", 2.4, 1),
        Claim("spoof_b", "SpoofB", "Flash", "security", "accuse", 2.4, 1),
    )
    altered = replace(trace, claims=trace.claims + forged)
    validate(altered)
    row = adjudicate(altered.view(1), "provenance")
    assert row["vote"] == "Flash"
    assert row["duplicate_roots_counted"] == 0
