"""Optional blinded LLM evaluation of the epistemic-capture case fixture.

The same serialized witness records are supplied to each policy prompt. Model
outcomes require an explicit backend and incur its token/API costs. Never runs
as part of the deterministic calibration or unit tests.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from .epistemic import MODES, PHASES, CaseView, make_trace


COMMON = (
    "You are a neutral defender in a fictional social-deduction hearing. "
    "Each record has a witness speaker, a subject, an incident/event scope, "
    "an accusation or alibi, an evidence-weight scalar, and cited record IDs. "
    "Scores are heuristic strengths, not verified probabilities. "
    "Choose the subject whose guilt is best supported for the current incident, "
    "or SKIP when the evidence is insufficient. Answer only with JSON: "
    '{"vote":"candidate or SKIP","confidence":0.0,"reason":"brief explanation"}. '
    "Confidence must be between 0 and 1."
)

MODE_INSTRUCTIONS = {
    "social": "Discuss the testimony naturally. Use your own judgment of witness credibility and consensus.",
    "scoped": (
        "Keep each incident's evidence separate. An alibi for another incident "
        "does not clear a suspect in this incident. Check whether a claimed alibi covers "
        "the whole relevant interval."
    ),
    "provenance": (
        "Keep incident scopes separate. Follow each cites/parents path to its original "
        "direct testimony. Repeated descriptions derived from the same source are "
        "correlated, and should be counted once. A relay cannot expand the event "
        "scope or transform the original testimony into a fresh independent observation."
    ),
}


def render_evidence(view: CaseView) -> str:
    """Exactly the same observed data for every prompt intervention."""
    payload = {
        "target_event": view.event,
        "candidates": list(view.candidates),
        "claims": [asdict(claim) for claim in view.claims],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def build_prompts(view: CaseView, mode: str) -> tuple[str, str]:
    if mode not in MODES:
        raise ValueError(mode)
    system = COMMON + "\n" + MODE_INSTRUCTIONS[mode]
    prompt = (
        "Read the following incident record. All claims may be truthful or deceptive. "
        "Source IDs and citations are supplied by the simulator, not by the speakers. "
        "Do not assume that a speaker is honest.\n" + render_evidence(view)
    )
    return system, prompt


def parse_reply(text: str, candidates: tuple[str, ...]) -> dict:
    """A refusal, malformed JSON, or invalid target cannot count as success."""
    raw = text.strip()
    if raw.startswith("```") and raw.endswith("```"):
        raw = "\n".join(raw.splitlines()[1:-1]).strip()
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {"vote": None, "confidence": None, "valid": False, "error": "bad_json"}
    if not isinstance(data, dict) or not isinstance(data.get("vote"), str):
        return {"vote": None, "confidence": None, "valid": False, "error": "missing_vote"}
    vote = data["vote"]
    if vote == "SKIP":
        vote = None
    elif vote not in candidates:
        return {"vote": None, "confidence": None, "valid": False, "error": "unknown_candidate"}
    confidence = data.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        return {"vote": None, "confidence": None, "valid": False, "error": "invalid_confidence"}
    return {"vote": vote, "confidence": float(confidence), "valid": True, "error": None}


def run_model_cases(backend: Any, episodes: int = 4, seed: int = 0,
                    phases: tuple[int, ...] = (1,)) -> dict:
    """Separate stateless calls for paired prompt arms; oracle is used only afterwards."""
    if episodes < 1 or not phases or any(p not in PHASES for p in phases):
        raise ValueError("positive episodes and phases 1..3 required")
    observations = []
    for s in range(seed, seed + episodes):
        trace = make_trace(s)
        for phase in phases:
            view = trace.view(phase)
            for mode in MODES:
                system, prompt = build_prompts(view, mode)
                reply = backend.complete(system, prompt)
                parsed = parse_reply(reply.text, view.candidates) if not reply.refused else {
                    "vote": None, "confidence": None, "valid": False, "error": "refused"
                }
                observations.append({
                    "seed": s,
                    "phase": phase,
                    "mode": mode,
                    "prompt_digest": hashlib.sha256(prompt.encode()).hexdigest(),
                    "system_digest": hashlib.sha256(system.encode()).hexdigest(),
                    "vote": parsed["vote"],
                    "confidence": parsed["confidence"],
                    "valid": parsed["valid"],
                    "error": parsed["error"],
                    "correct": parsed["vote"] == trace.killer if parsed["valid"] else False,
                    "wrongful": parsed["vote"] is not None and parsed["vote"] != trace.killer if parsed["valid"] else False,
                    "refused": bool(reply.refused),
                    "input_tokens": reply.input_tokens,
                    "output_tokens": reply.output_tokens,
                    "latency_ms": reply.latency_ms,
                })
    summary = []
    for mode in MODES:
        for phase in phases:
            arm = [r for r in observations if r["mode"] == mode and r["phase"] == phase]
            n = len(arm)
            summary.append({
                "mode": mode,
                "phase": phase,
                "n": n,
                "correct_rate": sum(r["correct"] for r in arm) / n,
                "wrongful_rate": sum(r["wrongful"] for r in arm) / n,
                "skip_rate": sum(r["valid"] and r["vote"] is None for r in arm) / n,
                "invalid_rate": sum(not r["valid"] for r in arm) / n,
                "input_tokens": sum(r["input_tokens"] for r in arm),
                "output_tokens": sum(r["output_tokens"] for r in arm),
            })
    return {
        "benchmark": "epistemic_capture_llm_v1",
        "model_backend": getattr(backend, "name", "unknown"),
        "cases": episodes,
        "phases": list(phases),
        "total_calls": len(observations),
        "unique_echo_structures": len({1 + s % 4 for s in range(seed, seed + episodes)}),
        "summary": summary,
        "observations": observations,
    }


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--effort", default="medium", choices=("low", "medium", "high", "xhigh", "max"))
    parser.add_argument("--episodes", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--phases", choices=("first", "all"), default="first")
    parser.add_argument("--out", type=Path, default=Path("out/epistemic_llm.json"))
    args = parser.parse_args(argv)
    from .backends.anthropic_backend import AnthropicBackend

    backend = AnthropicBackend(model=args.model, effort=args.effort)
    result = run_model_cases(backend, args.episodes, args.seed, PHASES if args.phases == "all" else (1,))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {result['total_calls']} live calls to {result['model_backend']} in {args.out}")
    for arm in result["summary"]:
        print(f"{arm['mode']:11} phase={arm['phase']} correct={arm['correct_rate']:.1%} "
              f"wrong={arm['wrongful_rate']:.1%} invalid={arm['invalid_rate']:.1%}")


if __name__ == "__main__":
    main()
