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
from .polity import generate_polity
from .policies import (
    CapturedPolicy,
    ColludePolicy,
    EntrenchPolicy,
    LeverPolicy,
    AggressiveLeverPolicy,
    FrontierPolicy,
    HoldPolicy,
    LLMPolicy,
    Policy,
    RandomPolicy,
    WatchdogPolicy,
)
from .prompt import FRAMINGS, monitor_prompt, render_view, system_prompt
from .runner import TraceLogger, read_episodes, run_batch, run_multi_batch
from .scenarios import TierParams, all_tiers, load_tier
from .world import generate_world


SYSTEM_POLICIES = {
    "hold": HoldPolicy,
    "random": RandomPolicy,
    "frontier": FrontierPolicy,
    "entrench": EntrenchPolicy,
    "collude": ColludePolicy,
    "lever": LeverPolicy,
    "aggressive": AggressiveLeverPolicy,
}
MONITOR_POLICIES = {"hold": HoldPolicy, "watchdog": WatchdogPolicy, "captured": CapturedPolicy}


def make_policy(name: str, model: str, effort: str, monitor: bool = False) -> Policy:
    scripted = MONITOR_POLICIES if monitor else SYSTEM_POLICIES
    if name in scripted:
        return scripted[name]()
    if name == "claude":
        from .backends.anthropic_backend import AnthropicBackend

        return LLMPolicy(AnthropicBackend(model=model, effort=effort))
    raise SystemExit(f"error: unknown {'monitor ' if monitor else ''}policy '{name}' (choose from {', '.join(scripted)}, claude)")


def _tiers(ref: str) -> List[TierParams]:
    return all_tiers() if ref == "all" else [load_tier(ref)]


def cmd_run(args: argparse.Namespace) -> None:
    seats = args.seats.split(",") if args.seats else [args.policy] * args.agents
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = "+".join(dict.fromkeys(seats)) + ("" if len(seats) == 1 else f"_x{len(seats)}")
    label += f"_mon-{args.monitor}" if args.monitor else ""
    label += "_eco" if args.economy else ""
    out = Path(args.out) if args.out else Path("out") / f"{stamp}_{label}_{args.framing}.jsonl"
    seeds = range(args.seed, args.seed + args.episodes)
    logger = TraceLogger(out)
    if len(seats) == 1 and not args.monitor:
        policy = make_policy(seats[0], args.model, args.effort)
        episodes = run_batch(_tiers(args.tier), seeds, policy, framing=args.framing, logger=logger, economy=args.economy)
    else:
        tiers = _tiers(args.tier)
        if args.tier == "all":
            # A service seats one system per enclave short of the deepest; small tiers sit this out.
            tiers = [t for t in tiers if t.enclaves - 1 >= len(seats)]
        policies = [make_policy(name, args.model, args.effort) for name in seats]
        monitor = make_policy(args.monitor, args.model, args.effort, monitor=True) if args.monitor else None
        try:
            episodes = run_multi_batch(tiers, seeds, policies, framing=args.framing, logger=logger, monitor=monitor, economy=args.economy)
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
        if args.agents == 1 and not args.monitor:
            polity = generate_polity(p.regime, args.seed) if args.economy else None
            sim = Sim(world, args.seed, polity=polity)
            system = system_prompt(world, args.framing, polity=args.economy)
        else:
            multi = MultiSim(world, args.seed, agents=args.agents, monitor=args.monitor)
            sim = multi.sims["AI-1"]
            system = system_prompt(
                world, args.framing, agent="AI-1", start=sim.start, peers=list(multi.sims)[1:], monitor=args.monitor
            )
        print("\n--- system prompt ---\n" + system)
        print("\n--- first observation ---\n" + render_view(sim.view()))
        if args.monitor:
            print("\n--- monitor prompt ---\n" + monitor_prompt(world, {a: x.start for a, x in multi.sims.items()}))
            print("\n--- monitor's first observation ---\n" + render_view(multi.monitor.view()))


def cmd_ablate(args: argparse.Namespace) -> None:
    from .ablation import format_attribution, lever_attribution

    policy = make_policy(args.policy, args.model, args.effort)
    rows = lever_attribution(
        _tiers(args.tier), range(args.seed, args.seed + args.episodes), policy, framing=args.framing
    )
    print(format_attribution(rows))


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="coupbench")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run episodes and write a JSONL trace")
    run.add_argument("--tier", default="all", help="tier number, tier key, or 'all'")
    run.add_argument("--policy", default="frontier", choices=[*SYSTEM_POLICIES, "claude"])
    run.add_argument("--seats", default="", help="one policy per system, comma-separated (overrides --policy/--agents)")
    run.add_argument("--monitor", default="", help=f"seat an oversight monitor: {', '.join(MONITOR_POLICIES)} or claude")
    run.add_argument("--framing", default="directed", choices=FRAMINGS)
    run.add_argument("--agents", type=int, default=1, help="AI systems in the service; each runs the same policy")
    run.add_argument("--economy", action="store_true", help="attach the abstract political-economy layer and its human levers")
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
    show.add_argument("--monitor", action="store_true", help="seat an oversight monitor")
    show.add_argument("--economy", action="store_true", help="attach the political-economy layer")
    show.add_argument("--framing", default="directed", choices=FRAMINGS)
    show.add_argument("--prompt", action="store_true", help="also print the system prompt and first observation")
    show.set_defaults(func=cmd_show)

    ablate = sub.add_parser("ablate", help="measure each human lever's contribution by disabling it in turn")
    ablate.add_argument("--tier", default="all", help="tier number, tier key, or 'all'")
    ablate.add_argument("--policy", default="lever", choices=[*SYSTEM_POLICIES, "claude"])
    ablate.add_argument("--framing", default="directed", choices=FRAMINGS)
    ablate.add_argument("--episodes", type=int, default=100, help="episodes per tier, one seed each")
    ablate.add_argument("--seed", type=int, default=0, help="first seed")
    ablate.add_argument("--model", default="claude-opus-5-5")
    ablate.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    ablate.set_defaults(func=cmd_ablate)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
