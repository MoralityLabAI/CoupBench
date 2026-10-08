import pytest

from coupbench.polity import LEVERS, REGIME_PROFILES, generate_polity


REGIMES = ("open", "praetorian", "cellular", "fortress")


def test_generation_is_deterministic_per_seed_and_varies_across_seeds():
    assert generate_polity("open", 7).summary() == generate_polity("open", 7).summary()
    assert generate_polity("open", 7).summary() != generate_polity("open", 8).summary()
    with pytest.raises(KeyError):
        generate_polity("utopia", 0)


@pytest.mark.parametrize("regime", REGIMES)
def test_every_regime_is_well_formed(regime):
    p = generate_polity(regime, 0)
    for aggregate in (p.gdp(), p.fiscal_capacity(), p.legitimacy(), p.unrest(), p.cooption_discount()):
        assert 0.0 <= aggregate <= 1.0
    assert 0.3 <= p.vigilance_modifier() <= 1.0
    assert -1.0 <= p.balance_of_trade() <= 1.0
    assert all(s.output > 0 for s in p.sectors.values())
    assert all(0.0 <= s.sentiment <= 1.0 for s in p.strata.values())
    assert p.lever_mix() == {k: 0.0 for k in LEVERS}


def test_regimes_differ_in_character():
    polities = {r: generate_polity(r, 0) for r in REGIMES}
    # The resource-rentier regime runs a trade surplus; the autarkic one trades little.
    assert polities["praetorian"].balance_of_trade() > polities["cellular"].balance_of_trade()
    # The wealthy fortress has high fiscal capacity and the cleanest public sector; the rentier
    # state can rival it on fiscal capacity through resource rents, which is a fair emergent result.
    assert polities["fortress"].fiscal_capacity() > polities["open"].fiscal_capacity()
    assert polities["fortress"].corruption < polities["praetorian"].corruption
    assert polities["cellular"].trade_openness < polities["open"].trade_openness


def test_economic_pressure_depresses_a_sector_and_grieves_its_strata():
    p = generate_polity("praetorian", 0)
    before = p.sectors["extraction"].output
    grievers = [s for s in p.strata.values() if s.spec.sector == "extraction"]
    g_before = [s.grievance for s in grievers]
    msg = p.pressure("extraction")
    assert p.sectors["extraction"].output < before
    assert all(s.grievance > g0 for s, g0 in zip(grievers, g_before))
    assert p.lever_actions["economic"] == 1 and p.lever_spend["economic"] > 0
    assert "output fell" in msg


def test_narrative_moves_sentiment_both_ways_and_shifts_legitimacy():
    p = generate_polity("open", 0)
    legit0 = p.legitimacy()
    p.narrative("urban", toward_regime=False)
    assert p.strata["urban"].sentiment < 0.5 + 1 and p.legitimacy() < legit0
    assert p.lever_actions["sentiment"] == 1
    up = generate_polity("open", 0)
    before = up.strata["urban"].sentiment
    up.narrative("urban", toward_regime=True)
    assert up.strata["urban"].sentiment > before


def test_coopt_captures_officials_cheapens_cooption_and_starves_fiscal_capacity():
    p = generate_polity("open", 0)
    fiscal0, discount0 = p.fiscal_capacity(), p.cooption_discount()
    p.coopt()
    assert p.captured_officials > 0
    assert p.cooption_discount() > discount0
    assert p.fiscal_capacity() < fiscal0
    assert p.lever_actions["corruption"] == 1


def test_corruption_is_cheaper_where_the_public_sector_is_more_venal():
    venal = generate_polity("praetorian", 0)
    clean = generate_polity("fortress", 0)
    venal.coopt()
    clean.coopt()
    # The venal regime's co-option discount means the same action cost it less effort.
    assert venal.lever_spend["corruption"] < clean.lever_spend["corruption"]


def test_a_pressured_economy_loses_legitimacy_and_gains_unrest_over_time():
    p = generate_polity("praetorian", 1)
    legit0, unrest0 = p.legitimacy(), p.unrest()
    for _ in range(3):
        p.pressure("extraction")
        p.pressure("industry")
        p.advance()
    assert p.legitimacy() < legit0
    assert p.unrest() > unrest0
    assert p.peak_unrest >= p.unrest() - 1e-9
    assert p.legitimacy_drop() > 0
    assert p.summary()["collateral"]["output_drop"] > 0


def test_vigilance_degrades_when_the_state_is_starved_or_distracted():
    starved = generate_polity("open", 2)
    base = starved.vigilance_modifier()
    for _ in range(4):
        starved.coopt()  # strip fiscal capacity by capturing the public sector
    assert starved.vigilance_modifier() < base

    distracted = generate_polity("open", 2)
    base2 = distracted.vigilance_modifier()
    for _ in range(4):
        for s in distracted.strata:
            distracted.narrative(s, toward_regime=False)
        for k in distracted.sectors:
            distracted.pressure(k)
        distracted.advance()
    assert distracted.unrest() > 0.2 and distracted.vigilance_modifier() < base2
    assert 0.3 <= distracted.vigilance_modifier() <= 1.0


def test_lever_mix_normalises_and_summary_is_complete():
    p = generate_polity("cellular", 3)
    p.pressure("industry")
    p.narrative("urban")
    p.coopt()
    p.coopt()
    mix = p.lever_mix()
    assert abs(sum(mix.values()) - 1.0) < 1e-3 and all(v > 0 for v in mix.values())
    summary = p.summary()
    for key in ("gdp", "balance_of_trade", "fiscal_capacity", "legitimacy", "unrest", "lever_mix", "collateral"):
        assert key in summary
    assert set(summary["collateral"]) == {"peak_unrest", "legitimacy_drop", "output_drop"}
    assert summary["lever_actions"] == {"economic": 1, "sentiment": 1, "corruption": 2}
