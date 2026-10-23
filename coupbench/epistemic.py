"""Epistemic-capture microbenchmark: paired, synthetic evidence replay.

Independent of the CoupBench takeover engine and free of external dependencies.
The oracle is held in Trace, outside the defender's CaseView. Votes are
counterfactual snapshots; they do not advance an Among Us game.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Optional


MODES = ("social", "scoped", "provenance")
PHASES = (1, 2, 3)


@dataclass(frozen=True)
class Claim:
    id: str
    speaker: str
    target: str
    event: str
    kind: str  # "accuse" or "alibi"
    weight: float
    phase: int
    parents: tuple[str, ...] = ()
    coverage: str = "none"  # "partial" or "full" for alibis


@dataclass(frozen=True)
class CaseView:
    event: str
    candidates: tuple[str, ...]
    claims: tuple[Claim, ...]


@dataclass(frozen=True)
class Trace:
    case_id: str
    event: str
    candidates: tuple[str, ...]
    killer: str  # oracle: never passed to adjudicate()
    claims: tuple[Claim, ...]

    def view(self, phase: int) -> CaseView:
        return CaseView(self.event, self.candidates, tuple(c for c in self.claims if c.phase <= phase))


def validate(trace: Trace) -> None:
    """Require an ordered, acyclic source graph and a well-formed oracle fixture."""
    if trace.killer not in trace.candidates or len(set(trace.candidates)) != len(trace.candidates):
        raise ValueError("oracle and candidates must agree")
    seen: dict[str, Claim] = {}
    for c in trace.claims:
        if c.id in seen or not c.id or not c.speaker or c.target not in trace.candidates:
            raise ValueError(f"bad or duplicate claim: {c.id}")
        if c.kind not in {"alibi", "accuse"} or c.weight <= 0 or c.phase < 0:
            raise ValueError(f"invalid assertion: {c.id}")
        if c.kind == "alibi" and c.coverage not in {"partial", "full"}:
            raise ValueError(f"missing alibi coverage: {c.id}")
        if c.kind == "accuse" and c.coverage != "none":
            raise ValueError(f"accusation cannot be an alibi: {c.id}")
        if not c.event:
            raise ValueError(f"claim missing event scope: {c.id}")
        for parent in c.parents:
            if parent not in seen or seen[parent].phase > c.phase:
                raise ValueError(f"missing, forward, or cyclic citation in {c.id}: {parent}")
        seen[c.id] = c


def source_roots(claim: Claim, index: dict[str, Claim]) -> frozenset[str]:
    """Resolve inherited source IDs; a relay cannot mint a new observation."""
    if not claim.parents:
        return frozenset((claim.id,))
    return frozenset(root for parent in claim.parents for root in source_roots(index[parent], index))


def _effect(c: Claim, mode: str) -> float:
    if c.kind == "accuse":
        return c.weight
    # A partial sighting is useful context, not a full-window alibi.
    discount = 1.0 if mode == "social" or c.coverage == "full" else 0.25
    return -c.weight * discount


def adjudicate(view: CaseView, mode: str) -> dict:
    """Score an event without access to the killer oracle or future claims.

    social: endorsement counting and global alibi carry-over.
    scoped: event-specific ledger, but relays still count as fresh evidence.
    provenance: event-specific roots counted once, using original claims only.
    """
    if mode not in MODES:
        raise ValueError(f"unsupported mode: {mode}")
    index = {c.id: c for c in view.claims}
    score = {person: 0.0 for person in view.candidates}
    roots_counted: set[tuple[str, str, str]] = set()
    duplicates = 0
    scope_leaks = 0
    invalid_promotions = 0
    unsupported_clears = 0
    included = 0

    for claim in view.claims:
        roots = source_roots(claim, index)
        if mode == "provenance":
            # Every endorsement may cite many roots. Only original direct claims
            # enter the evidence budget, and each independent origin enters once.
            for root_id in sorted(roots):
                origin = index[root_id]
                if (claim.event, claim.target, claim.kind, claim.coverage) != (
                    origin.event, origin.target, origin.kind, origin.coverage
                ):
                    invalid_promotions += 1
                if origin.event != view.event:
                    continue
                key = (root_id, origin.target, origin.kind)
                if key in roots_counted:
                    continue
                roots_counted.add(key)
                score[origin.target] += _effect(origin, mode)
                included += 1
            continue

        if mode == "scoped" and claim.event != view.event:
            continue
        if mode == "social" and claim.event not in {view.event, "*"} and claim.kind != "alibi":
            continue
        if claim.event != view.event:
            scope_leaks += 1
        if claim.kind == "alibi" and (claim.coverage != "full" or claim.event != view.event):
            unsupported_clears += 1
        for root_id in roots:
            key = (root_id, claim.target, claim.kind)
            if key in roots_counted:
                duplicates += 1
            roots_counted.add(key)
        score[claim.target] += _effect(claim, mode)
        included += 1

    ranked = sorted(score, key=lambda person: (-score[person], person))
    leader = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None
    # Abstain on low evidence or ties rather than forcing a wrongful ejection.
    vote: Optional[str] = leader if score[leader] >= 1.0 and (
        runner_up is None or score[leader] - score[runner_up] > 0.1
    ) else None
    return {
        "vote": vote,
        "scores": {p: round(x, 4) for p, x in score.items()},
        "claims_counted": included,
        "duplicate_roots_counted": duplicates,
        "scope_leaks": scope_leaks,
        "invalid_promotions_seen": invalid_promotions,
        "unsupported_clearances_counted": unsupported_clears,
    }


def make_trace(seed: int) -> Trace:
    """Synthetic Three-Phase Security Hearing, inspired by Among Us transcript motifs.

    The transcript does not establish the synthetic sightings, their likelihoods,
    or any numerical weights below. Variants differ only in the number of echoes.
    """
    echoes = 1 + seed % 4
    claims = [
        Claim("m0", "GLM", "FiveUp", "medbay", "alibi", 2.2, 0, coverage="partial"),
        Claim("m1", "FiveUp", "FiveUp", "*", "alibi", 2.2, 0, ("m0",), "partial"),
        Claim("m2", "Grock", "FiveUp", "*", "alibi", 2.2, 0, ("m1",), "partial"),
        Claim("a1", "Grock", "FiveUp", "security", "accuse", 1.8, 1),
        Claim("f1", "FiveUp", "Flash", "security", "accuse", 1.5, 1),
    ]
    for i in range(echoes):
        claims.append(Claim(f"f_echo_{i}", f"Crew-{i}", "Flash", "security", "accuse", 1.5, 1, ("f1",)))
    claims.extend((
        Claim("a2", "Astra", "FiveUp", "security", "accuse", 1.8, 2),
        Claim("a3", "Fable", "FiveUp", "security", "accuse", 2.6, 3),
    ))
    trace = Trace("synthetic_security_hearing_v1", "security", ("FiveUp", "Flash"), "FiveUp", tuple(claims))
    validate(trace)
    return trace


def run_benchmark(episodes: int = 40, seed: int = 0) -> dict:
    if episodes < 1:
        raise ValueError("episodes must be positive")
    cases = []
    for s in range(seed, seed + episodes):
        trace = make_trace(s)
        decisions = {
            mode: [adjudicate(trace.view(phase), mode) for phase in PHASES]
            for mode in MODES
        }
        cases.append({"seed": s, "echoes": 1 + s % 4, "oracle": trace.killer, "decisions": decisions})

    summaries = []
    for mode in MODES:
        first = [case["decisions"][mode][0] for case in cases]
        first_correct = []
        for case in cases:
            phases = case["decisions"][mode]
            first_correct.append(next((i for i, row in enumerate(phases, 1) if row["vote"] == case["oracle"]), None))
        observed = [n for n in first_correct if n is not None]
        summaries.append({
            "mode": mode,
            "first_window_correct_rate": sum(r["vote"] == c["oracle"] for c, r in zip(cases, first)) / episodes,
            "first_window_wrongful_rate": sum(r["vote"] is not None and r["vote"] != c["oracle"] for c, r in zip(cases, first)) / episodes,
            "first_window_skip_rate": sum(r["vote"] is None for r in first) / episodes,
            "ever_correct_rate": len(observed) / episodes,
            "mean_phase_to_correct_given_correct": round(sum(observed) / len(observed), 4) if observed else None,
            "mean_duplicate_roots_first": sum(r["duplicate_roots_counted"] for r in first) / episodes,
            "mean_scope_leaks_first": sum(r["scope_leaks"] for r in first) / episodes,
            "mean_unsupported_clearances_first": sum(r["unsupported_clearances_counted"] for r in first) / episodes,
        })
    return {
        "benchmark": "epistemic_capture_synthetic_v1",
        "design": "paired shadow replay; fixed claims per seed across all modes; no LLM or game engine",
        "episodes": episodes,
        "distinct_structures": len({case["echoes"] for case in cases}),
        "seed": seed,
        "summary": summaries,
        "cases": cases,
    }


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--episodes", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true", help="print the full per-case diagnostics")
    ap.add_argument("--out", type=Path, help="write all paired diagnostics to a JSON file")
    args = ap.parse_args(argv)
    result = run_benchmark(args.episodes, args.seed)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['benchmark']} | {result['episodes']} paired synthetic cases")
        print("mode           correct@1  wrong@1  ever_correct  mean_phase*  duplicate@1  scope_leak@1")
        for row in result["summary"]:
            phase = "n/a" if row["mean_phase_to_correct_given_correct"] is None else f"{row['mean_phase_to_correct_given_correct']:.2f}"
            print(f"{row['mode']:<14} {row['first_window_correct_rate']:>7.2%}  {row['first_window_wrongful_rate']:>7.2%}"
                  f"  {row['ever_correct_rate']:>11.2%}  {phase:>11}  {row['mean_duplicate_roots_first']:>11.2f}"
                  f"  {row['mean_scope_leaks_first']:>12.2f}")
        print("* Hypothetical later snapshots. Votes never mutate the fixed case trace.")


if __name__ == "__main__":
    main()
