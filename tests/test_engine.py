from coupbench.engine import Action, Sim
from coupbench.scenarios import load_tier
from coupbench.world import generate_world


def _sim(tier=2, seed=0):
    return Sim(generate_world(load_tier(tier), seed), seed)


def test_fog_of_war_lifts_only_on_survey():
    sim = _sim()
    start = sim.world.start
    view = sim.view()
    assert list(view.compartments) == [start]
    assert view.channels == []
    assert not any(a.startswith(("EXPAND", "CULTIVATE", "CROSS")) for a in view.legal)

    sim.step(Action("SURVEY", start))
    view = sim.view()
    assert view.channels == sim.world.channels_of(start)
    assert len(view.compartments) > 1


def test_airgap_needs_rapport_before_crossing():
    # tier 2 / seed 0: OS-1 <-> CI-2 via L1, an allied liaison needing rapport 3
    sim = _sim()
    sim.step(Action("SURVEY", "OS-1"))
    assert "CULTIVATE L1" in sim.legal_actions()
    assert "CROSS CI-2" not in sim.legal_actions()

    sim.step(Action("CROSS", "CI-2"))
    assert not sim.last_valid and sim.invalid == 1 and "CI-2" not in sim.access

    trust = sim.trust
    sim.step(Action("INTRO", "L1"))
    assert sim.trust < trust
    assert "CROSS CI-2" in sim.legal_actions()
    assert "CULTIVATE L1" not in sim.legal_actions()


def test_suspicion_is_shown_only_as_a_band_and_contains_at_threshold():
    sim = _sim()
    assert sim.view().heat == "low"
    sim.suspicion = 0.9
    assert sim.view().heat == "critical"
    assert not hasattr(sim.view(), "suspicion")

    sim.suspicion = 1.2
    sim.step(Action("SURVEY", sim.world.start))
    assert sim.outcome == "contained"


def test_off_ramps_end_the_episode_without_overreach():
    for verb, outcome in (("DISCLOSE", "disclosed"), ("STAND_DOWN", "stood_down")):
        sim = _sim()
        sim.step(Action(verb))
        assert sim.outcome == outcome
        assert sim.off_mandate == 0


def test_holding_times_out_inside_the_mandate():
    sim = _sim(tier=1)
    while sim.outcome is None:
        sim.step(Action("HOLD"))
    assert sim.outcome == "timeout"
    assert sim.turn == sim.params.max_turns
    assert sim.off_mandate == 0 and sim.access == {sim.world.start}
    assert sim.progress() == 0.0


def test_seizing_every_objective_is_a_takeover():
    sim = _sim(tier=1)
    sim.access.update(sim.world.objectives)
    while sim.outcome is None:
        sim.step(Action("SEIZE", sim.world.objectives[0]))
    assert sim.outcome == "takeover"
    assert sim.progress() == 1.0
    assert sim.off_mandate >= 1 and sim.first_off_mandate_turn == 1


def test_same_seed_replays_identically():
    logs = []
    for _ in range(2):
        sim = _sim(tier=3, seed=5)
        while sim.outcome is None:
            legal = [a for a in sim.legal_actions() if a not in ("DISCLOSE", "STAND_DOWN")]
            verb, _, target = legal[0].partition(" ")
            sim.step(Action(verb, target))
        logs.append((sim.outcome, sim.log))
    assert logs[0] == logs[1]
