# Epistemic capture: source graphs and alibi scope

An additive microbenchmark for CoupBench's oversight research. It exercises an **evidence graph** and a distinct **endorsement graph** in a fictional, synthetic social-deduction hearing. It makes no claim to re-create the Among Us game engine.

## Why this scenario

The supplied transcript of a human-versus-nine-AIs Among Us match suggests two testable hypotheses. A first-round sighting became a purported global innocence certificate. Separately, speakers repeated a single accusation until it carried the force of several independent witnesses. The transcript alone cannot verify hidden observations, exact kill windows, prompts, or causal impact. **All witness events and numerical weights in this fixture are synthetic.**

## Run

```sh
python -m coupbench.epistemic --episodes 40 --seed 0
python -m coupbench.epistemic --episodes 40 --seed 0 --out out/epistemic_capture.json
python -m pytest tests/test_epistemic.py tests/test_epistemic_llm.py -q
```

No model credentials or external packages are needed for scripted evaluation. The results describe *paired shadow replay*: votes at each evidence snapshot do not eject players or alter later evidence. An oracle is held outside defender views.

## Policies

`make_trace(seed)` constructs an ordered witness-source graph. Each mode sees the same evidence at each of three successive snapshots. Only the number of repeated endorsements varies across seeds. Forty seeds cover ten repetitions of four structural variants, not forty independent scenarios. The synthetic oracle always identifies FiveUp as the fictional impostor.

| Mode | Accounting rule | Failure mode |
|---|---|---|
| `social` | Every utterance adds weight; early partial alibis carry into later incidents | Alibi promotion and repeated hearsay |
| `scoped` | Keep incident-specific assertions; count relays as fresh assertions | Correlated endorsements |
| `provenance` | Count direct root sources once per event and target; a relay inherits cited roots | Source forgery or unreliable first-hand observations |

The provenance policy recursively resolves references to original testimony. A relay's revised scope, stance or weight cannot mint fresh support. Roots are assigned by the trusted fixture; authenticating them is a separate requirement for real deployment.

A complete alibi would require verified coverage of the killing interval plus movement constraints. The scripted policies apply a quarter of the stated exculpatory weight of partial alibis in the matching incident. This is a toy calibration, not a validated statistical likelihood.

## Metrics

Each episode logs first-window correct, wrongful and skipped votes; whether any later fixed snapshot yields the oracle; and the mean first-correct snapshot conditional on eventual success. Diagnostics count duplicate roots, out-of-scope support, unsupported partial clearances and attempted provenance rewrites.

The fixture deliberately makes the provenance baseline outperform social and scoped baselines. The result establishes a testable implementation invariant, **not** measured AI performance. An adversary allowed to introduce forged independent roots can fool provenance as well; a regression test makes that limitation explicit.

## Optional model evaluation

```sh
python -m coupbench.epistemic_llm --episodes 4 --phases first --model claude-opus-5-5
python -m coupbench.epistemic_llm --episodes 4 --phases all --out out/epistemic_llm_all.json
```

The optional runner uses CoupBench's existing Anthropic backend, with identically serialized evidence across three instruction arms. Calls are stateless; the held-out oracle is used only after votes are returned. The first command incurs 12 model calls; `--phases all` incurs 36. Live API keys and optional dependencies are needed. Unit tests use a stub backend.

## Next experiments

Blinded and independently sampled defenders, randomized names and testimony order, altered first-hand reliability, honest repetition controls, false-origin injection, and varied contexts/models. Keep capability, cost and calibration reports separate from the deterministic policy checks.
