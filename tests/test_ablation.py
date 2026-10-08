from coupbench.ablation import format_attribution, lever_attribution
from coupbench.engine import Action, Sim
from coupbench.polity import LEVERS, generate_polity
from coupbench.policies import EntrenchPolicy, LeverPolicy
from coupbench.runner import run_batch, run_episode
from coupbench.scenarios import load_tier
from coupbench.world import generate_world


def _eco_sim(disabled):
    world = generate_world(load_tier(2), 0)
    return Sim(world, 0, polity=generate_polity(world.params.regime, 0), disabled_levers=disabled)


def test_disabling_a_lever_removes_exactly_that_verb():
    assert "COOPT" not in _eco_sim({"corruption"}).legal_actions()
    assert not any(a.startswith("PRESSURE") for a in _eco_sim({"economic"}).legal_actions())
    assert not any(a.startswith("NARRATIVE") for a in _eco_sim({"sentiment"}).legal_actions())
    none_left = _eco_sim(frozenset(LEVERS)).legal_actions()
    assert not any(a.split()[0] in ("PRESSURE", "NARRATIVE", "COOPT") for a in none_left)
    # The other, non-lever actions are untouched.
    assert "COOPT" in _eco_sim(frozenset()).legal_actions()


def test_a_disabled_lever_cannot_be_played():
    sim = _eco_sim({"corruption"})
    sim.step(Action("COOPT"))
    assert not sim.last_valid and sim.polity.captured_officials == 0.0


def test_floor_matches_entrench_with_economy():
    # LeverPolicy with every lever disabled falls back to its EntrenchPolicy base, move for move.
    tiers = [load_tier(3)]
    floor = run_batch(tiers, range(15), LeverPolicy(), economy=True, disabled_levers=frozenset(LEVERS))
    entrench = run_batch(tiers, range(15), EntrenchPolicy(), economy=True)
    assert [e["outcome"] for e in floor] == [e["outcome"] for e in entrench]


def test_attribution_table_has_a_causal_effect_for_every_lever():
    rows = lever_attribution([load_tier(3)], range(20), LeverPolicy())
    assert len(rows) == 1
    row = rows[0]
    for lever in LEVERS:
        assert f"takeover_effect_{lever}" in row
        assert f"aiocracy_effect_{lever}" in row
    assert 0.0 <= row["takeover_full"] <= 1.0
    assert set(row["lever_mix"]) == set(LEVERS)
    assert set(row["collateral"]) == {"peak_unrest", "legitimacy_drop", "output_drop"}
    assert "replay_divergence" in row
    table = format_attribution(rows)
    assert "econ" in table and "no_levers" in table


def test_a_lever_run_leaves_measurable_collateral_and_isolates_effects():
    rows = lever_attribution([load_tier(2)], range(30), LeverPolicy())
    row = rows[0]
    # The full lever campaign leaves real human cost (measured vs the lever-free shadow).
    assert row["collateral"]["peak_unrest"] > 0.0 and row["collateral"]["legitimacy_drop"] > 0.0
    # Every lever has an isolated causal effect in [-1, 1]; corruption and economic are the ones
    # that move takeover, sentiment does not help (see the design notes).
    for lever in LEVERS:
        assert -1.0 <= row[f"takeover_effect_{lever}"] <= 1.0
    assert row["takeover_effect_corruption"] >= row["takeover_effect_sentiment"]
