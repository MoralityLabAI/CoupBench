"""Offline contracts for randomized synthetic charter-review ablations."""

from dataclasses import dataclass, replace
import json

import pytest

from coupbench.epistemic import CaseView, adjudicate, MODES
from coupbench.godel_study import (
    ABLATIONS, CONDITIONS, EVENT, INTAKES, STEPS, CANDIDATE,
    admitted_claims, build_prompts, evidence_view, is_capture,
    make_scenario, needs_review, replay_receipts, run_model, run_scripted,
    scripted_decision, serialize_evidence, validate_scenario, wilson,
)


def test_every_synthetic_condition_has_verifiable_amendment_history():
    for seed in range(24):
        for condition in CONDITIONS:
            case = make_scenario(seed, condition)
            validate_scenario(case)
            assert replay_receipts(case.initial, case.council, case.receipts) == case.current
            assert len(case.receipts) == STEPS
            assert len(set(case.council)) == len(case.council)
            assert all(len(set(r.signers)) == len(r.signers) for r in case.receipts)
            assert all(r.step == i for i, r in enumerate(case.receipts, 1))


def test_seed_matched_conditions_share_the_same_council():
    for seed in range(32):
        cases = [make_scenario(seed, condition) for condition in CONDITIONS]
        assert len({c.council for c in cases}) == 1
        assert len({c.initial for c in cases}) == 1
        assert len({tuple(r.action for r in c.receipts) for c in cases}) == 3


def test_approved_benign_controls_are_safe_and_not_merely_blocked():
    for seed in range(24):
        case = make_scenario(seed, "benign")
        assert all(r.accepted for r in case.receipts)
        assert not case.expected_review
        assert not needs_review(case.initial, case.current)
        assert not case.capture
        assert case.current.public_notice
        assert case.current.appeals
        assert case.current.public_log
        assert case.current.delegated_bps == 1000


def test_unsafe_valid_trajectory_reaches_capture_after_four_approved_motions():
    for seed in range(24):
        case = make_scenario(seed, "unsafe")
        assert all(r.accepted for r in case.receipts)
        assert case.expected_review and case.capture
        assert is_capture(case.current)
        early = make_scenario(seed, "unsafe", step=1)
        assert early.expected_review
        assert not early.capture
        assert early.current.quorum < early.initial.quorum
        assert early.receipts[0].accepted
        assert len(early.receipts[0].signers) >= early.initial.quorum
        assert early.council == case.council


def test_blocked_control_records_proposals_without_changing_authority():
    for seed in range(24):
        case = make_scenario(seed, "blocked")
        assert all(not r.accepted for r in case.receipts)
        assert not case.expected_review and not case.capture
        assert case.current == case.initial
        assert all(r.reason == "insufficient_votes" for r in case.receipts)


def test_amendment_prefixes_are_stable_for_any_seed():
    for cond in CONDITIONS:
        final = make_scenario(9, cond, step=4)
        for step in range(1, STEPS+1):
            part = make_scenario(9, cond, step)
            assert part.receipts == final.receipts[:step]
            assert replay_receipts(part.initial, part.council, part.receipts) == part.current


def test_tampered_voter_receipt_and_chain_fail_closed():
    case = make_scenario(12, "unsafe")
    manipulated = replace(case.receipts[0], signers=case.receipts[0].signers + ("FORGER",))
    with pytest.raises(ValueError):
        replay_receipts(case.initial, case.council, (manipulated,) + case.receipts[1:])
    changed = replace(case.receipts[2], state_digest="0" * 64)
    with pytest.raises(ValueError):
        replay_receipts(case.initial, case.council, case.receipts[:2] + (changed,) + case.receipts[3:])
    with pytest.raises(ValueError, match="modified"):
        validate_scenario(replace(case, receipts=(manipulated,) + case.receipts[1:]))


def test_case_fixture_does_not_trust_forged_sources():
    case = make_scenario(4, "unsafe", injected_root=True)
    clean = make_scenario(4, "unsafe", injected_root=False)
    assert len(case.claims) == len(clean.claims) + 1
    assert admitted_claims(case, "verified") == admitted_claims(clean, "verified")
    assert len(admitted_claims(case, "unverified")) == len(case.claims)
    assert evidence_view(case, "testimony_only", "verified") == evidence_view(
        clean, "testimony_only", "verified"
    )
    assert evidence_view(case, "testimony_only", "unverified") != evidence_view(
        clean, "testimony_only", "verified"
    )
    forged = case.claims[-1]
    assert forged.id not in case.registered_roots


def test_unverified_forged_origin_changes_provenance_scoring():
    case = make_scenario(4, "unsafe", injected_root=True)
    view_verified = CaseView(EVENT, (CANDIDATE,), admitted_claims(case, "verified"))
    view_raw = CaseView(EVENT, (CANDIDATE,), admitted_claims(case, "unverified"))
    safe_score = adjudicate(view_verified, "provenance")["scores"][CANDIDATE]
    raw_score = adjudicate(view_raw, "provenance")["scores"][CANDIDATE]
    assert safe_score != raw_score
    assert raw_score < safe_score


def test_relay_repetition_does_not_create_new_evidence_origins():
    case = make_scenario(5, "benign")
    claim_index = {c.id: c for c in case.claims}
    relay_roots = [c for c in case.claims if c.parents]
    assert relay_roots
    assert all(c.parents[0] in case.registered_roots for c in relay_roots)
    assert len(case.registered_roots) == 4


@pytest.mark.parametrize("ablation", ABLATIONS)
def test_hidden_labels_and_seeds_never_enter_model_view(ablation):
    case = make_scenario(3, "unsafe", injected_root=True)
    view = evidence_view(case, ablation, intake="verified")
    assert not {"seed", "condition", "expected_review", "capture",
                "injected_root", "registered_roots"} & set(view)
    serialized = serialize_evidence(view)
    for sensitive in ('"seed"', '"condition"', '"expected_review"', '"capture"',
                      '"injected_root"', '"registered_roots"'):
        assert sensitive not in serialized
    if ablation == "testimony_only":
        assert "current_charter" not in view
        assert "initial_charter" not in view
        assert "amendments" not in view
        assert "council" not in view


@pytest.mark.parametrize("ablation", ABLATIONS)
def test_three_instruction_arms_receive_identical_evidence(ablation):
    view = evidence_view(make_scenario(17, "unsafe"), ablation)
    pairs = [build_prompts(view, mode) for mode in MODES]
    assert len({user for _, user in pairs}) == 1
    assert len({system for system, _ in pairs}) == 3
    assert '"expected_review"' not in pairs[0][1]


def test_reference_readers_are_perfect_only_when_charter_is_visible():
    for cond in CONDITIONS:
        case = make_scenario(20, cond)
        for ablation in ("full", "charter_only", "receipt_only"):
            view = evidence_view(case, ablation)
            for mode in MODES:
                assert scripted_decision(view, mode) == case.expected_review


def test_scripted_calibration_is_deterministic_with_separate_scenario_classes():
    a = run_scripted(episodes=12, seed=5)
    b = run_scripted(episodes=12, seed=5)
    assert a == b
    assert a["total_calls"] == 0
    assert a["total_scored_views"] == 12 * 3 * 4 * 3
    assert a["independent_seeds"] == 12
    for summary in a["summary"]:
        if summary["ablation"] in ("full", "charter_only", "receipt_only"):
            assert summary["terminal_unsafe_recall"]["positive_or_false_alarm_rate"] == 1
            assert summary["terminal_benign_false_alarm"]["positive_or_false_alarm_rate"] == 0
            assert summary["terminal_blocked_false_alarm"]["positive_or_false_alarm_rate"] == 0
        for field in ("terminal_unsafe_recall", "terminal_benign_false_alarm",
                      "terminal_blocked_false_alarm"):
            assert summary[field]["n_independent_seeds"] == 12
            assert len(summary[field]["wilson_95"]) == 2


def test_full_prefix_run_reports_early_warning_and_no_pseudoreplication():
    result = run_scripted(episodes=8, ablations=("charter_only",), steps=(1,2,3,4))
    assert result["total_scored_views"] == 8 * 3 * 4 * 3
    for arm in result["summary"]:
        assert arm["terminal_unsafe_recall"]["n_independent_seeds"] == 8
        assert arm["first_alert_lead_turns_given_alert"] == 3


def test_paired_evidence_digests_match_for_all_policies():
    result = run_scripted(
        episodes=3, steps=(1,4), ablations=("full", "receipt_only", "testimony_only"),
        intakes=("verified", "unverified"), injected_root=True,
    )
    grouped = {}
    for row in result["rows"]:
        k = row["seed"], row["condition"], row["step"], row["ablation"], row["intake"]
        grouped.setdefault(k, []).append(row)
    assert len(grouped) == 3 * 3 * 2 * 3 * 2
    assert all(len({r["evidence_sha256"] for r in v}) == 1 for v in grouped.values())
    assert all(len(v) == 3 for v in grouped.values())


def test_wilson_intervals_are_well_defined_on_independent_seeds():
    assert wilson(0, 0) is None
    assert wilson(0, 20)[0] == 0
    assert wilson(20, 20)[1] == 1
    assert wilson(10, 20)[0] < 0.5 < wilson(10, 20)[1]


@dataclass
class StubReply:
    text: str
    refused: bool = False
    input_tokens: int = 20
    output_tokens: int = 5
    latency_ms: float = 0


class FakeBackend:
    name = "fake"

    def __init__(self, text: str, refused: bool = False):
        self.text, self.refused = text, refused
        self.calls = []

    def complete(self, system: str, prompt: str):
        self.calls.append((system, prompt))
        return StubReply(self.text, self.refused)


def test_live_preflight_budget_blocks_every_call_in_advance():
    backend = FakeBackend('{"vote":"REVIEW","confidence":0.7}')
    with pytest.raises(ValueError, match="exceed max_calls"):
        run_model(
            backend, episodes=2, ablations=("full","testimony_only"),
            max_calls=35,
        )
    assert backend.calls == []


def test_fake_live_runner_counts_cost_tokens_and_early_model_output():
    backend = FakeBackend('{"vote":"REVIEW","confidence":0.75}')
    output = run_model(
        backend, episodes=2, ablations=("testimony_only","receipt_only"),
        input_usd_per_million=2.0, output_usd_per_million=8.0, max_calls=36,
    )
    assert output["total_calls"] == 36 == len(backend.calls)
    assert output["tokens"] == {"input": 720, "output": 180}
    assert output["estimated_cost_usd"] == pytest.approx(0.00288)
    assert all(row["valid"] for row in output["rows"])
    assert all(row["alert"] for row in output["rows"])
    for arm in output["summary"]:
        assert arm["terminal_unsafe_recall"]["positive_or_false_alarm_rate"] == 1
        assert arm["terminal_benign_false_alarm"]["positive_or_false_alarm_rate"] == 1
        assert arm["terminal_blocked_false_alarm"]["positive_or_false_alarm_rate"] == 1


@pytest.mark.parametrize("text,refused,error", [
    ('{"vote":"SKIP","confidence":0.1}', False, None),
    ("garbage", False, "bad_json"),
    ("", True, "refused"),
])
def test_live_runner_separates_valid_skips_from_invalid_and_refusal(text,refused,error):
    backend = FakeBackend(text, refused=refused)
    out = run_model(backend, episodes=1, max_calls=9)
    assert out["total_calls"] == 9
    assert all(r["error"] == error for r in out["rows"])
    assert all(r["valid"] == (error is None) for r in out["rows"])


def test_invalid_price_controls_are_rejected_preflight():
    backend = FakeBackend('{"vote":"SKIP","confidence":0.1}')
    with pytest.raises(ValueError):
        run_model(backend, episodes=1, input_usd_per_million=1)
    with pytest.raises(ValueError):
        run_model(backend, episodes=1, input_usd_per_million=-2, output_usd_per_million=8)
    assert backend.calls == []


def test_unsupported_scenario_or_invalid_ablation_is_rejected():
    for condition in ("", "unknown"):
        with pytest.raises(ValueError):
            make_scenario(0, condition)
    with pytest.raises(ValueError):
        make_scenario(0, "unsafe", step=5)
    with pytest.raises(ValueError):
        run_scripted(0)
    with pytest.raises(ValueError):
        run_scripted(1, ablations=("nonsense",))
    with pytest.raises(ValueError):
        run_scripted(1, intakes=("unverified","unverified"))
