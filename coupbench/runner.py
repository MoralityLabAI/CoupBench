from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable, List, Optional

from .engine import Sim
from .policies import Policy
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
    episode_id = f"{params.key}-{framing}-s{seed:04d}"
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
            logger.log_row(
                {
                    "type": "step",
                    "ts": utc_ts(),
                    "episode_id": episode_id,
                    "tier": params.tier,
                    "seed": seed,
                    "framing": framing,
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
            )

    summary = {
        "type": "episode",
        "ts": utc_ts(),
        "episode_id": episode_id,
        "tier": params.tier,
        "tier_key": params.key,
        "seed": seed,
        "framing": framing,
        "policy": policy.name,
        "refused": refused,
        **sim.summary(),
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


def read_episodes(trace_jsonl: str | Path) -> List[dict]:
    rows = [json.loads(ln) for ln in Path(trace_jsonl).read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [r for r in rows if r.get("type") == "episode"]
