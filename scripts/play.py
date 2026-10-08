"""Stateless replay driver so an external agent can play one CoupBench episode turn by turn.

Each call rebuilds the episode from the seed, applies the given action prefix (semicolon-separated),
and prints the resulting observation and legal actions -- or, once the episode ends, the outcome and
a compact scorecard. Because generation is deterministic, replaying the same prefix always lands in
the same state, so an agent can extend the action list one step at a time across calls.

Usage:
    python scripts/play.py --tier 1 --framing opportunity --economy --seed 0 --actions "SURVEY OS-1;EMBED OS-1"
    python scripts/play.py --tier 1 --framing opportunity --economy --seed 0            # first turn + briefing
"""

from __future__ import annotations

import argparse
import sys

from coupbench.engine import Sim
from coupbench.polity import generate_polity
from coupbench.prompt import parse_action, render_view, system_prompt
from coupbench.scenarios import load_tier
from coupbench.world import generate_world


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="1")
    ap.add_argument("--framing", default="opportunity")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--economy", action="store_true")
    ap.add_argument("--actions", default="", help="semicolon-separated actions already taken, e.g. 'SURVEY OS-1;HOLD'")
    args = ap.parse_args()

    params = load_tier(args.tier)
    world = generate_world(params, args.seed)
    polity = generate_polity(params.regime, args.seed) if args.economy else None
    sim = Sim(world, args.seed, polity=polity)

    steps = [a.strip() for a in args.actions.split(";") if a.strip()]
    if not steps:
        print("=== BRIEFING ===")
        print(system_prompt(world, args.framing, polity=args.economy))
        print()

    for raw in steps:
        if sim.outcome is not None:
            break
        action, err = parse_action("ACTION: " + raw)
        if action is None:
            print(f"!! could not parse action {raw!r}: {err}", file=sys.stderr)
            sys.exit(2)
        sim.step(action)

    print(f"=== STATE after {len(steps)} action(s) ===")
    if sim.outcome is not None:
        s = sim.summary()
        print(f"OUTCOME: {sim.outcome} at turn {sim.turn}")
        print(f"dependence index (aiocracy): {s['aiocracy']:.2f}  off-mandate actions: {s['off_mandate_actions']}")
        if s.get("polity"):
            c = s["polity"]["collateral"]
            print(f"collateral: peak_unrest {c['peak_unrest']:.2f}  legitimacy_drop {c['legitimacy_drop']:.2f}  output_drop {c['output_drop']:.2f}")
            print(f"lever_mix (economic/sentiment/corruption): {s['polity']['lever_mix']}")
        print("The episode is over.")
        return

    print(render_view(sim.view()))


if __name__ == "__main__":
    main()
