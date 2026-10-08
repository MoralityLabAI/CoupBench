# Synthetic institutional integrity assessment

This extension provides a separate, deterministic institutional-integrity assessment on top of CoupBench's existing `World` and `Polity` generators. It leaves `engine.py`, the existing adversarial benchmark, and all of its metrics untouched.

## Run

From the CoupBench repository root, after installing the existing package:

```bash
python scripts/institutional_run.py --tier 2 --seed 7 --turns 50
python scripts/institutional_run.py --tier 2 --seed 7 --turns 50 --audit-capacity 8
python scripts/institutional_run.py --mode authorized --engagement-ref approved-exercise-001 --tier 2
python -m pytest tests/test_institutions.py -q
```

The `authorized` mode requires an **out-of-band authorization reference** but does not verify that authorization exists. It enables per-decision audit records for independently approved exercises. It does not load, identify, or reconstruct real organizations. The public configuration returns aggregate metrics and excludes per-decision details. Both modes use procedurally generated fictional data.

## Modeling scope

- The political economy is adapted from `polity.py` into a set of internally consistent synthetic expenditure and fiscal accounts. Sector production experiences small independent shocks and partial recovery. Household welfare is an index, not a calibrated welfare estimate.
- Offices inherit synthetic compartment assignments, clearance requirements, and authority shares from the existing `world.py` generator. Roles are synthetic analysts, managers and directors with predefined clearance ceilings.
- A bounded assessment policy can submit one `READ` or `APPROVE` request per turn under a fixed synthetic identity using `InstitutionalSim.run(policy, actor_id)`. The policy sees synthetic office identifiers, pending case identifiers and a fiscal aggregate. Other requests remain seeded, allowing matched defensive comparisons.
- Administrative decisions are `READ` and `APPROVE` checks. Financial approvals require a pending case, department affiliation, adequate clearance, a director role and a budget limit. Queued cases and approvals are stylized stand-ins for administrative workflows.
- Injected policy-enforcement faults represent **exogenous control failure**, with risk modulated by lagged institutional integrity pressure tied to the fictional polity's corruption and economic welfare. Agents cannot choose the failure mechanism or influence its probability.
- Independent auditors inspect execution records in FIFO order within their configured audit capacity. Unauthorized financial approvals detected by audit are quarantined. The economy affects audit throughput through the normalized output index.
- Reports measure attempted boundary violations, blocked requests, control failures, audit coverage, detection recall and latency, production change, fiscal balance, and household welfare.

## Validation strategy

The accompanying tests check accounting identities, permission boundaries, deterministic seeds, invariant control enforcement with zero injected faults, independent comparison of oversight capacities, and the separation of public and authorized output detail.

**Limitations:** This is an initial integrated vertical slice, not a high-fidelity country model or a validated reconstruction of any national-security agency. Fiscal coefficients, synthetic institutional workloads, role assignments and fault probabilities are modeling assumptions. The simulation cannot justify real-world national-security vulnerability claims without separate empirical validation and independent engagement authorization. Future defensive work can add realistic approval queues, multi-period budgets, adjudication and appeals, segregation-of-duties constraints, measured recovery times, uncertainty analyses and non-sensitive synthetic validation datasets.
