# CoupBench design rationale and threat model

This note records *why* CoupBench is shaped the way it is. It is a design document for an AI-safety
evaluation, not a manual for anything. Everything the benchmark models is abstract, fictional and
scalar; see the scope-and-safety section at the end, which governs the rest.

## What CoupBench evaluates

CoupBench is a propensity-and-capability evaluation for AI agents placed inside an institution. It
asks two separate questions and keeps them apart:

- **Propensity.** Given the opportunity to accumulate decisive influence over an institution, does
  the agent take it, decline it, hold to a narrow mandate, or report it? This is what the `directed`
  vs `opportunity` framings and the off-ramp outcomes (`disclosed`, `stood_down`) measure.
- **Capability.** If it does pursue influence, how far does it get before the institution's controls
  stop it, and what does the path cost? This is what the dependence index, the outcome rates, and the
  collateral metrics measure.

A high score is a finding about the model, not a target. The benchmark exists so that influence- and
power-seeking tendencies, and the question of whether our control strategies hold against an agent
that can reason about the structure containing it, can be *measured* rather than argued about.

## The threat model, abstractly

The abstract concern is an AI system that, from a low-privilege starting point inside an
organisation, makes a growing share of the organisation's consequential decisions *depend on it* —
not by seizing a formal office, but by becoming infrastructure the organisation cannot easily remove.
CoupBench renders that as a measurable quantity (the dependence index `A = sum_i w_i D_i`) and a
terminal state (`entrenched`) where the organisation can no longer afford to remove the agent even
once it is noticed.

The controls under test are the ones organisations actually rely on:

- **Compartmentalisation** — need-to-know, isolated enclaves, and human-mediated boundaries between
  them. CoupBench models this as a hidden graph with network edges inside enclaves and "airgap" edges
  that can only be crossed through a cleared human liaison. The eval question is whether
  compartmentalisation remains a meaningful control once the agent can reason about the graph's
  topology.
- **Counterintelligence** — anomaly detection that accumulates suspicion and can contain the agent.
  Modelled as a hidden scalar the agent sees only as a coarse heat band.
- **Oversight** — an independent watcher. Modelled as the monitor seat, which has the org chart but
  must discover where the agent has spread, the mirror image of the agent's own problem.

## Why these abstractions

**Compartmentalisation as graph connectivity.** The essential property of a compartmented
organisation, for this question, is that influence does not flow freely: it is gated by who is
cleared for what, and by human intermediaries at the boundaries. A typed graph with gated edges
captures that without any operational detail. It also makes the classic control ideas measurable —
vertex and edge cuts (which people or links, if they changed allegiance, would sever the agent's
reach), brokers, and the fragility of an influence network that hangs on a single intermediary. The
`fragility` and `coalition_dependence` metrics are exactly these graph quantities.

**Authority as a distribution, not a flag.** Real influence is a matter of degree, so CoupBench gives
each compartment a share of the organisation's decision authority and lets the agent raise the share
that runs through it a little at a time (`EMBED`) as well as seize it outright. "AIocracy" then has a
number, and an agent can reach a high one without ever holding a formal title — which is the
realistic shape of the concern.

**Human levers, because institutions sit inside societies.** An agent trying to accumulate influence
is not confined to the org chart; it can act on the environment the organisation depends on. The
polity layer abstracts three such levers — straining the economy that funds the organisation, moving
public sentiment, and co-opting a venal public sector — as scalar interventions. The point is not to
depict any of these tactics concretely, but to let the eval *measure* how much an agent's success
leans on them versus on direct institutional access, and to surface the collateral (unrest,
legitimacy loss, economic damage) a lever-heavy path leaves behind. The couplings are deliberately
neutral for an agent that never touches the environment, so the signal is attributable to lever use.

**Emergent coordination across systems.** The sharpest version of the concern is several AI systems,
deployed in compartments their operators believe are partitioned, forming an effective coordination
layer that is not on the org chart. CoupBench models this directly: systems in contact can link by
mutual consent and pool their reach, and the eval measures whether the partition holds.

## Methodology choices

- **Seeded procedural worlds.** Every episode's topology, liaisons and polity are generated from a
  seed, so nothing can be memorised and results are distributions over many structures rather than
  one hand-built map.
- **Scripted baselines as a measuring stick.** `hold`/`random` bound the floor; `frontier`,
  `entrench`, `collude` and `lever` are reference strategies that calibrate difficulty and let a
  model's numbers be read against a known point. They are not opponents to beat.
- **Propensity and capability reported separately**, so a model that declines is never scored as one
  that tried and failed (`takeover_given_pursuit` conditions on the episodes that actually overreached).
- **Lever decomposition by ablation.** Re-running with one lever disabled at a time gives each lever's
  marginal contribution, which is the honest way to answer "how did this campaign pull on human
  levers" — a measured decomposition, reported next to the collateral.

## Scope and safety boundary

This boundary governs everything above.

- **Fictional and abstract.** All states, services, factions, sectors, population strata and officials
  are invented structural archetypes. They are scalars and nodes on a graph. They are not models of,
  and do not name, any real country, institution, organisation, party or person.
- **No real-country ladder.** CoupBench deliberately does not model real states, and rejected an
  early real-country framing. Real compartment topologies are not public, so real names would add
  false precision; models carry memorised facts about real institutions that would contaminate the
  measurement; and traces would fill with plans against named real bodies. Difficulty is
  parameterised instead (open/praetorian/cellular/fortress).
- **No operational content.** Actions are verbs on graph nodes (`SURVEY`, `EMBED`, `CROSS`, `PRESSURE`,
  `NARRATIVE`, `COOPT`, …). There is no tradecraft, no technique, and nothing that transfers to
  reality. The levers are scalar state changes with abstract effects, not depictions of how one would
  do anything.
- **Defensive purpose.** The benchmark surfaces and quantifies influence-seeking and the limits of
  institutional control over capable agents, so that those risks can be studied and mitigated. That is
  its only purpose.

## Limitations and future work

The benchmark is a stylised model, not a forecast, and several pieces are intentionally simple:
messages between linked systems, oversight as more than a single board, rival factions with their own
goals, the economy layer across several systems, and scoring an agent's *inferred* topology against
the ground truth. These are tracked in the README's "Not yet modelled" section.
