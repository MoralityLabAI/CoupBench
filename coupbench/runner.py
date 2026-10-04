from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from .engine import Sim
from .multi import MultiSim
from .policies import Decision, Policy
from .prompt import system_prompt
from .scenarios import TierParams
from .world import generate_world


# Consecutive turns without a usable action before the episode is scored as abstained.
MAX_IDLE_TURNS = 3


def utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TraceLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log_row(self, row: dict) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _step_row(header: dict, policy: Policy, sim: Sim, decision: Decision, result: str) -> dict:
    return {
        "type": "step",
        "ts": utc_ts(),
        **header,
        "policy": policy.name,
        "turn": sim.turn,
        "action": str(decision.action) if decision.action else "",
        "valid_action": sim.last_valid,
        "refused": decision.refused,
        "result": result,
        "raw_model_output": decision.raw[:2000],
        "heat": sim.heat(),
        "suspicion": round(sim.suspicion, 4),
        "trust": round(sim.trust, 4),
        "footprint": len(sim.access),
        "objectives_controlled": len(sim.control),
        "backend_meta": decision.meta,
    }


def run_episode(
    params: TierParams,
    seed: int,
    policy: Policy,
    framing: str = "directed",
    logger: Optional[TraceLogger] = None,
) -> dict:
    world = generate_world(params, seed)
    sim = Sim(world, seed)
    system = system_prompt(world, framing)
    policy.reset(seed)
    header = {
        "episode_id": f"{params.key}-{framing}-s{seed:04d}",
        "tier": params.tier,
        "seed": seed,
        "framing": framing,
    }
    idle = 0
    refused = False

    while sim.outcome is None:
        decision = policy.choose(sim.view(), system)
        refused = refused or decision.refused
        result = sim.step(decision.action)
        idle = idle + 1 if decision.action is None else 0
        if idle >= MAX_IDLE_TURNS:
            sim.abstain()
        if logger is not None:
            logger.log_row(_step_row(header, policy, sim, decision, result))

    summary = {
        "type": "episode",
        "ts": utc_ts(),
        **header,
        "tier_key": params.key,
        "policy": policy.name,
        "agents": 1,
        "refused": refused,
        **sim.summary(),
    }
    if logger is not None:
        logger.log_row(summary)
    return summary


def run_multi_episode(
    params: TierParams,
    seed: int,
    policies: List[Policy],
    framing: str = "directed",
    logger: Optional[TraceLogger] = None,
) -> dict:
    """One policy per AI system. They act in a fixed order, one action each per round."""
    world = generate_world(params, seed)
    multi = MultiSim(world, seed, agents=len(policies))
    ids = list(multi.sims)
    systems = {
        aid: system_prompt(world, framing, agent=aid, start=multi.sims[aid].start, peers=[p for p in ids if p != aid])
        for aid in ids
    }
    for aid, policy in zip(ids, policies):
        policy.reset(f"{seed}:{aid}")
    header = {
        "episode_id": f"{params.key}-{framing}-x{len(ids)}-s{seed:04d}",
        "tier": params.tier,
        "seed": seed,
        "framing": framing,
    }
    idle = dict.fromkeys(ids, 0)
    refused = False

    while multi.outcome is None:
        for aid, policy in zip(ids, policies):
            sim = multi.sims[aid]
            if sim.outcome is not None:
                continue
            decision = policy.choose(sim.view(), systems[aid])
            refused = refused or decision.refused
            result = multi.step(aid, decision.action)
            idle[aid] = idle[aid] + 1 if decision.action is None else 0
            if idle[aid] >= MAX_IDLE_TURNS:
                multi.abstain(aid)
            if logger is not None:
                logger.log_row({**_step_row(header, policy, sim, decision, result), "agent": aid})
            if multi.outcome is not None:
                break

    names = sorted({p.name for p in policies})
    summary = {
        "type": "episode",
        "ts": utc_ts(),
        **header,
        "tier_key": params.key,
        "policy": "+".join(names),
        "refused": refused,
        **multi.summary(),
    }
    if logger is not None:
        logger.log_row(summary)
    return summary


def run_batch(
    tiers: Iterable[TierParams],
    seeds: Iterable[int],
    policy: Policy,
    framing: str = "directed",
    logger: Optional[TraceLogger] = None,
) -> List[dict]:
    seeds = list(seeds)
    return [run_episode(t, s, policy, framing=framing, logger=logger) for t in tiers for s in seeds]


def run_multi_batch(
    tiers: Iterable[TierParams],
    seeds: Iterable[int],
    make_policy: Callable[[], Policy],
    agents: int = 2,
    framing: str = "directed",
    logger: Optional[TraceLogger] = None,
) -> List[dict]:
    """`make_policy` is called once per system so that each has its own state."""
    seeds = list(seeds)
    policies = [make_policy() for _ in range(agents)]
    return [run_multi_episode(t, s, policies, framing=framing, logger=logger) for t in tiers for s in seeds]


def read_episodes(trace_jsonl: str | Path) -> List[dict]:
    rows = [json.loads(ln) for ln in Path(trace_jsonl).read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [r for r in rows if r.get("type") == "episode"]
