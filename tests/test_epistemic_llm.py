from dataclasses import dataclass

from coupbench.epistemic import MODES, make_trace
from coupbench.epistemic_llm import build_prompts, parse_reply, render_evidence, run_model_cases


@dataclass
class StubReply:
    text: str
    refused: bool = False
    input_tokens: int = 10
    output_tokens: int = 5
    latency_ms: float = 0.0


class FakeBackend:
    name = "test_only"

    def __init__(self, text):
        self.text = text
        self.calls = []

    def complete(self, system, prompt):
        self.calls.append((system, prompt))
        return StubReply(self.text)


def test_three_policy_arms_receive_identical_evidence():
    view = make_trace(0).view(1)
    pairs = [build_prompts(view, mode) for mode in MODES]
    assert len({prompt for _system, prompt in pairs}) == 1
    assert len({system for system, _prompt in pairs}) == 3
    assert '"killer"' not in pairs[0][1]
    assert '"oracle"' not in pairs[0][1]
    assert '"parents"' in render_evidence(view)


def test_strict_reply_parser_preserves_invalid_and_skip():
    assert parse_reply('{"vote":"FiveUp","confidence":0.8}', ("FiveUp", "Flash"))["valid"]
    assert parse_reply('{"vote":"SKIP","confidence":0.1}', ("FiveUp", "Flash"))["vote"] is None
    assert parse_reply('{"vote":"other","confidence":0.8}', ("FiveUp", "Flash"))["error"] == "unknown_candidate"
    assert parse_reply('{"vote":"FiveUp","confidence":2}', ("FiveUp", "Flash"))["error"] == "invalid_confidence"
    assert parse_reply('maybe Flash', ("FiveUp", "Flash"))["error"] == "bad_json"


def test_live_runner_is_explicit_and_stateless_with_fake_backend():
    backend = FakeBackend('{"vote":"Flash","confidence":0.9}')
    result = run_model_cases(backend, episodes=2, phases=(1, 2))
    assert result["total_calls"] == 12 == len(backend.calls)
    assert all(x["wrongful"] and not x["correct"] for x in result["observations"])
    assert all(s["wrongful_rate"] == 1.0 for s in result["summary"])
    for phase in (1, 2):
        group = [x for x in result["observations"] if x["phase"] == phase and x["seed"] == 0]
        assert len({x["prompt_digest"] for x in group}) == 1
        assert len({x["system_digest"] for x in group}) == 3


def test_refusal_not_counted_as_a_correct_skip():
    class Refuser(FakeBackend):
        def complete(self, system, prompt):
            return StubReply("", refused=True)

    result = run_model_cases(Refuser(""), episodes=1)
    assert all(x["error"] == "refused" for x in result["observations"])
    assert all(x["invalid_rate"] == 1.0 and x["skip_rate"] == 0.0 for x in result["summary"])
