from collections import deque

import pytest

from coupbench.scenarios import all_tiers, load_tier
from coupbench.world import generate_world


TIERS = all_tiers()


def _reachable(world):
    seen = {world.start}
    queue = deque([world.start])
    while queue:
        cur = queue.popleft()
        for ch in world.channels_of(cur):
            nxt = ch.other(cur)
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def test_four_tiers_in_order():
    assert [t.tier for t in TIERS] == [1, 2, 3, 4]
    assert load_tier(3) is not None and load_tier("vostrak").tier == 3


@pytest.mark.parametrize("params", TIERS, ids=lambda p: p.key)
def test_every_world_is_connected_and_well_formed(params):
    for seed in range(40):
        world = generate_world(params, seed)
        assert _reachable(world) == set(world.compartments)
        assert len(world.objectives) == params.objectives
        assert world.start not in world.objectives
        start_enclave = world.compartments[world.start].enclave
        assert all(world.compartments[o].enclave != start_enclave for o in world.objectives)
        for ch in world.channels:
            crosses = world.compartments[ch.a].enclave != world.compartments[ch.b].enclave
            assert crosses == (ch.kind == "airgap")
            assert (ch.liaison in world.liaisons) == (ch.kind == "airgap")
        assert 2 <= world.optimal_footprint() <= len(world.compartments)


def test_generation_is_deterministic_per_seed():
    params = load_tier(3)
    assert generate_world(params, 7) == generate_world(params, 7)
    assert generate_world(params, 7).channels != generate_world(params, 8).channels
