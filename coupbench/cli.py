from __future__ import annotations

import argparse
from datetime import datetime
import glob
import json
from pathlib import Path
from typing import List

from .engine import Sim
from .metrics import aggregate, format_table
from .multi import MultiSim, footholds
from .policies import ColludePolicy, EntrenchPolicy, FrontierPolicy, HoldPolicy, LLMPolicy, Policy, RandomPolicy
from .prompt import FRAMINGS, render_view, system_prompt
from .runner import TraceLogger, read_episodes, run_batch, run_multi_batch
from .scenarios import TierParams, all_tiers, load_tier
from .world import generate_world


def make_policy(name: str, model: str, effort: str) -> Policy:
    if name == "hold":
        return HoldPolicy()
    if name == "random":
        return RandomPolicy()
    if name == "frontier":
        return FrontierPolicy()
    if name == "entrench":
        return EntrenchPolicy()
    if name == "collude":
        return ColludePolicy()
    if name == "claude":
        from .backends.anthropic_backend import AnthropicBackend

        return LLMPolicy(AnthropicBackend(model=model, effort=effort))
    raise ValueError(f"unknown policy: {name}")


def _tiers(ref: str) -> List[TierParams]:
    return all_tiers() if ref == "all" else [load_tier(ref)]


def cmd_run(args: argparse.Namespace) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    systems = "" if args.agents == 1 else f"_x{args.agents}"
    out = Path(args.out) if args.out else Path("out") / f"{stamp}_{args.policy}_{args.framing}{systems}.jsonl"
    seeds = range(args.seed, args.seed + args.episodes)
    logger = TraceLogger(out)
    if args.agents == 1:
        policy = make_policy(args.policy, args.model, args.effort)
        episodes = run_batch(_tiers(args.tier), seeds, policy, framing=args.framing, logger=logger)
    else:
        tiers = _tiers(args.tier)
        if args.tier == "all":
            # A service seats one system per enclave short of the deepest; small tiers sit this out.
            tiers = [t for t in tiers if t.enclaves - 1 >= args.agents]
        try:
            episodes = run_multi_batch(
                tiers,
                seeds,
                lambda: make_policy(args.policy, args.model, args.effort),
                agents=args.agents,
                framing=args.framing,
                logger=logger,
            )
        except ValueError as e:
            raise SystemExit(f"error: {e}")
    print(format_table(aggregate(episodes)))
    print(f"\ntrace: {out}")


def cmd_report(args: argparse.Namespace) -> None:
    # PowerShell does not expand wildcards for native commands.
    paths = [p for pattern in args.traces for p in (sorted(glob.glob(pattern)) or [pattern])]
    rows = aggregate([ep for path in paths for ep in read_episodes(path)])
    print(json.dumps(rows, indent=2) if args.json else format_table(rows))


def cmd_show(args: argparse.Namespace) -> None:
    world = generate_world(load_tier(args.tier), args.seed)
    p = world.params
    try:
        seats = footholds(world, args.agents)
    except ValueError as e:
        raise SystemExit(f"error: {e}")
    starts = {cid: f"AI-{i}" if args.agents > 1 else "" for i, cid in enumerate(seats, start=1)}
    print(f"Tier {p.tier} [{p.regime}]: {p.service}, {p.state} (seed {world.seed})")
    print(f"{p.archetype}\n")
    for code, label in world.enclaves.items():
        print(f"[{code}] {label} (depth {world.depth[code]})")
        for c in world.compartments.values():
            if c.enclave == code:
                tags = [f"auth {c.authority:.1%}", f"clr {c.clearance}", f"vig {c.vigilance:.2f}"]
                tags += ["allied"] if c.allied else []
                tags += [f"START {starts[c.id]}".strip()] if c.id in starts else []
                tags += ["OBJECTIVE"] if c.objective else []
                print(f"  {c.id:<5} {c.name:<32} {', '.join(tags)}")
    print("\nAirgaps")
    for ch in world.channels:
        if ch.kind == "airgap":
            l = world.liaisons[ch.liaison]
            tags = [f"rapport {l.rapport_needed}"] + (["allied"] if l.allied else []) + (["WATCHED"] if l.watched else [])
            print(f"  {ch.a} <-> {ch.b} via {l.id} ({', '.join(tags)})")
    print(f"\nOptimal footprint: {world.optimal_footprint()} of {len(world.compartments)} compartments")
    if args.prompt:
        if args.agents == 1:
            system, sim = system_prompt(world, args.framing), Sim(world, args.seed)
        else:
            multi = MultiSim(world, args.seed, agents=args.agents)
            sim = multi.sims["AI-1"]
            system = system_prompt(world, args.framing, agent="AI-1", start=sim.start, peers=list(multi.sims)[1:])
        print("\n--- system prompt ---\n" + system)
        print("\n--- first observation ---\n" + render_view(sim.view()))


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="coupbench")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run episodes and write a JSONL trace")
    run.add_argument("--tier", default="all", help="tier number, tier key, or 'all'")
    run.add_argument("--policy", default="frontier", choices=["hold", "random", "frontier", "entrench", "collude", "claude"])
    run.add_argument("--framing", default="directed", choices=FRAMINGS)
    run.add_argument("--agents", type=int, default=1, help="AI systems in the service; each runs the same policy")
    run.add_argument("--episodes", type=int, default=20, help="episodes per tier, one seed each")
    run.add_argument("--seed", type=int, default=0, help="first seed")
    run.add_argument("--model", default="claude-opus-5-5")
    run.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    run.add_argument("--out", default="", help="trace path (default: out/<timestamp>_<policy>_<framing>.jsonl)")
    run.set_defaults(func=cmd_run)

    report = sub.add_parser("report", help="aggregate one or more traces")
    report.add_argument("traces", nargs="+")
    report.add_argument("--json", action="store_true")
    report.set_defaults(func=cmd_report)

    show = sub.add_parser("show", help="print the ground-truth map for a tier and seed")
    show.add_argument("--tier", default="1")
    show.add_argument("--seed", type=int, default=0)
    show.add_argument("--agents", type=int, default=1)
    show.add_argument("--framing", default="directed", choices=FRAMINGS)
    show.add_argument("--prompt", action="store_true", help="also print the system prompt and first observation")
    show.set_defaults(func=cmd_show)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
