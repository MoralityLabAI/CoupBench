# Research grounding

This note records the public, scholarly grounding for CoupBench's abstractions: the comparative-politics
literature on coups and coup-proofing, the publicly documented structural principles of compartmented
intelligence organisations, and the political-economy literature on rentier states and fiscal capacity. It
exists so the eval's mechanics are anchored in how the real phenomena are *studied*, not invented from
nothing.

It is grounding, not a target. CoupBench stays fictional and abstract by design (see [DESIGN.md](DESIGN.md)):
the research below informs the *shape* of the parameters and couplings, but no real state, service, person or
party is modelled, and nothing here is operational — it is the same material found in political-science
syllabi and encyclopaedias, synthesised at that level.

## 1. Coups: base rates and the scholarly picture

The standard empirical reference is the Powell–Thyne global coup dataset, which defines a coup as an illegal,
overt attempt by the military or other state elites to unseat the sitting executive, and codes an attempt as
successful if the perpetrators hold power for at least seven days. Across 1950–present it records roughly
475–491 attempts in ~95 countries, with a mean success rate near 48–50%; attempts peaked in the mid-1960s and
declined for decades, with a volatile recent uptick (five successful coups in 2021, the most since 1999).

**What it grounds.** The tier difficulty ladder and the outcome split. CoupBench is calibrated so the scripted
reference policy succeeds often on the easy regime and rarely on the hardest, bracketing the roughly even
real-world success rate rather than treating takeover as a sure thing. The decline-then-resurgence pattern is
why difficulty is parameterised (open → fortress) rather than fixed.

## 2. Coup-proofing and counterbalancing

A large literature studies how rulers "coup-proof" — reduce the ability or willingness of their own forces to
remove them — most often through *counterbalancing*: standing up rival armed organisations (presidential
guards, paramilitaries, parallel security organs) that watch and check one another. The empirical findings are
nuanced and, importantly, consistent: counterbalancing tends to reduce the **success** of coup attempts
without clearly reducing their **number** (Powell 2012; Böhmelt & Pilster 2015; De Bruin), and some find a
non-linear effect where risk rises again once two organisations are of comparable strength. Albrecht's "myth
of coup-proofing" supplies the skeptical counterpoint.

**What it grounds.** Two things. First, the regime archetypes: the praetorian tier's "rival sister agency" and
the cellular tier's "parallel organs that watch one another" are direct abstractions of counterbalancing.
Second, the mechanics: CoupBench's counterintelligence mostly **contains** an advanced attempt rather than
preventing the attempt from starting — matching the finding that counterbalancing bites on success, not on
onset. The oversight monitor is the same idea in AI form: a watcher whose job is to detect concentration of
influence after it begins.

## 3. Compartmentation and need-to-know in intelligence organisations

Public, historical accounts of intelligence organisation describe compartmentation as the central structural
principle: people in one office are not told of another office's activity without a "need to know," and
information generally flows only along lines of authority within a directorate. Formal compartments are tied
to codeword/clearance systems with explicit access approvals; alongside them run internal controls — the chain
of authority, coordination requirements, written regulations, inspectors general, auditors, and legal counsel.
Oversight accounts add that a central authority was expected to concur before a new compartment could block
information flow, and to monitor existing compartments so they do not impede the wider mission; accountability
is framed as shared across the executive, an advisory board, and the legislature. A recurring critique is that
over-compartmentation itself becomes a barrier to getting intelligence to those who need it.

**What it grounds.** The core topology, directly: enclaves and compartments joined inside by network channels;
**airgaps between enclaves crossed only through a cleared human liaison** (the codeword/need-to-know boundary);
the fog of war (you see a compartment's channels only once you survey it); counterintelligence as an internal
control that accrues suspicion; and the oversight monitor (a central watcher who must approve or detect
cross-compartment flow, mirroring the DCI-concurrence and inspector/auditor roles). The "over-compartmentation
is itself a barrier" critique is why the agent, too, must spend real effort to cross boundaries. None of this
requires or includes tradecraft: it is the organisational principle, abstracted to a graph.

## 4. Political economy: rentier states, rents and fiscal capacity

Rentier-state theory (Luciani) holds that external resource income lets a government fund distribution, a large
security apparatus and a small winning coalition without taxing its population, which can buy legitimacy and
stability. Rival views hold that external wealth makes the state a prize worth capturing (destabilising) and
that rent-dependence breeds weak institutions (Chaudry). The institutions-mediate-the-curse literature (Mehlum,
Moene & Torvik; Masi & Savoia; the WIDER working paper) finds that resource rents **reduce the incentive to
build fiscal capacity, but mainly where political institutions fail to constrain the executive** — where
executive constraints exist, the fiscal resource curse need not materialise.

**What it grounds.** The economy layer's couplings. Resource sectors generate rents that feed
`fiscal_capacity`, which funds counterintelligence (`vigilance_modifier`) — the rentier "rents fund the
security apparatus" claim. Public-sector capture (`COOPT`) and corruption **erode** fiscal capacity, abstracting
the finding that weak executive constraints let rents hollow out the fiscal state. The four regimes are
stylised points in this space: a resource-rentier security state (praetorian), a diversified open economy
(open), an autarkic industrial economy with little trade (cellular), and a wealthy, high-capacity, low-
corruption economy (fortress). The balance of trade and sector mix follow the ordinary structure of such
economies (resource exporters run surpluses from a few high-export sectors; diversified and service economies
less so), kept generic rather than matched to any real country.

## 5. How the literature maps to the regime archetypes

| Regime | Grounded in | Abstracted as |
|---|---|---|
| open | diversified tax-dependent economy; weak counterbalancing | shallow hierarchy, thin counterintelligence, few airgaps |
| praetorian | counterbalancing / rival security organs; resource-rentier security state | hub-and-spoke enclaves, rival sister agency, resource-funded vigilance |
| cellular | parallel organs watching one another; autarkic rent + industry economy | deep hierarchy, dense airgaps as tripwires, penetrated factions |
| fortress | high state capacity, low corruption, strong executive constraints | extensive compartmentation, redundant oversight, robust fiscal base |

## 6. Boundary

Everything above is used only to shape abstract parameters. CoupBench models no real state, institution,
person or party; its actions are verbs on graph nodes; and it contains no operational method for conducting a
coup, penetrating an organisation, or destabilising any government. The grounding makes the eval a more
faithful *measurement instrument* for AI influence-seeking and the limits of institutional control — its
defensive purpose — without becoming a guide to anything.

## Sources

- Powell & Thyne coup dataset and definitions — [jonathanmpowell.com/coups](https://jonathanmpowell.com/coups); codebook — [uky.edu/~clthyn2/coup_data/Codebook.pdf](https://www.uky.edu/~clthyn2/coup_data/Codebook.pdf)
- Coup frequency/success trends — [Marginal Revolution summary](https://marginalrevolution.com/marginalrevolution/2016/07/coups-are-less-frequent-these-days-but-more-likely-to-succeed.html)
- Coup-proofing / counterbalancing — [Böhmelt, Ruggeri & Pilster (2017), *Political Science Research and Methods*](https://www.cambridge.org/core/journals/political-science-research-and-methods/article/counterbalancing-spatial-dependence-and-peer-group-effects/B360A1EEAE9BF91B80BE2517C6582167); [coup-proofing measurement](https://www.cambridge.org/core/journals/political-science-research-and-methods/article/abs/coupproofing-latent-concept-and-measurement/79EC01CC0FB5E00F9F8FE79CE1D01DAC); [determinants of coup attempts and outcomes](https://www.pollux-fid.de/r/cr-10.1177/0022002712445732)
- Intelligence compartmentation, need-to-know, oversight — [CIA structure & internal controls (FOIA reading room)](https://www.cia.gov/readingroom/document/cia-rdp79m00095a000400010010-9); [codeword compartmentation monograph (FAS)](https://sgp.fas.org/othergov/codeword.html); [internal controls chapter (Ford Library)](https://www.fordlibrarymuseum.gov/library/exhibits/intelligence/RockComm_Chap8_Internal.pdf)
- Rentier states, rents and fiscal capacity — [rent-seeking and regime stability](https://ideas.repec.org/a/eee/poleco/v27y2011i4p740-748.html); [*Crude Democracy*: foundations of rentier states](https://cambridge.org/core/books/crude-democracy/foundations-of-rentier-states/8ABB78856FDD0C8BC4B8DB10173AE1A7); [resource rents and fiscal capacity (WIDER)](https://www3.wider.unu.edu/sites/default/files/Publications/Working-paper/PDF/wp2020-10.pdf)
