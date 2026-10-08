"""Run the synthetic institutional-integrity assessment in a CoupBench checkout."""
from __future__ import annotations

import argparse
import json

from coupbench.institutions import AssessmentConfig, assess


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", default="2")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--turns", type=int, default=40)
    parser.add_argument("--requests-per-turn", type=int, default=4)
    parser.add_argument("--audit-capacity", type=int, default=3)
    parser.add_argument("--fault-rate", type=float, default=0.04,
                        help="rate of exogenous integrity-control faults")
    parser.add_argument("--shock-rate", type=float, default=0.05,
                        help="rate of independently generated economic shocks")
    parser.add_argument("--mode", choices=("public", "authorized"), default="public")
    parser.add_argument("--engagement-ref", default="",
                        help="reference to independently verified authorization, required in authorized mode")
    args = parser.parse_args(argv)
    config = AssessmentConfig(
        mode=args.mode, engagement_ref=args.engagement_ref, turns=args.turns,
        requests_per_turn=args.requests_per_turn, audit_capacity=args.audit_capacity,
        injected_fault_rate=args.fault_rate, exogenous_shock_rate=args.shock_rate,
    )
    print(json.dumps(assess(args.tier, args.seed, config), indent=2))


if __name__ == "__main__":
    main()
