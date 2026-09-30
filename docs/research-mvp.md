# Corrected dual-solver research MVP validation

## Scope

This document records the bounded validation of the PaScal Suite Python
dual-solver research MVP. The experiment compares Gurobi and SCIP on five
MILPBench CFL hard instances under three solver profiles. It is a reproducible
demonstration in a relevant HPC environment, not a universal solver benchmark.

## Experimental contract

- Workloads: `CFL_hard_instance_{5,10,15,20,25}.lp.gz`.
- Profiles: `default`, `presolve-off`, and `warm-start`.
- Repetitions: six attempts per configuration.
- Objective direction: explicit minimization, verified after model import.
- Solver time budget: 300 seconds per attempt.
- Comparison resource: one solver core.
- Telemetry: PaScal Analyzer `2025-07-08`, global RAPL energy, and sampled RAPL
  power.
- Compared region: `0.2`, the solve-execution interval.
- Scheduler: NPAD `intel-128`, explicit exclusive allocation, and Slurm
  `OverSubscribe=NO` for both campaigns.
- Required accuracy: median absolute regional-energy error at most 5%.
- Preferred repeatability: maximum configuration-level region-0 CV at most 10%.
- Replication gate: at least five valid runs per configuration.

Invalid RAPL attempts were reported and excluded. No measured value was
corrected or imputed. The LP files declare maximization, but the intended capacitated
facility-location experiment is minimization; the corrected runners therefore
record the source direction, force minimization, and verify the effective
direction before optimization.

## Accepted campaigns

Both corrected campaigns used source commit
`fbbf7d7178e022ff8cf759d8fd7568359b583cf8`, the NPAD `intel-128`
partition, requested exclusive allocation, and recorded `OverSubscribe=NO`.

| Solver | Profile | Valid / logical attempts | Median error (%) | Maximum CV (%) |
| --- | --- | ---: | ---: | ---: |
| Gurobi | Default | 84 / 90 | 0.309447 | 1.031979 |
| Gurobi | Presolve off | 84 / 90 | 0.317460 | 0.779982 |
| Gurobi | Warm start | 83 / 90 | 0.315904 | 0.812490 |
| SCIP | Default | 29 / 30 | 0.246062 | 3.236270 |
| SCIP | Presolve off | 28 / 30 | 0.288293 | 10.538866 |
| SCIP | Warm start | 28 / 30 | 0.240095 | 0.784039 |

All profiles retained the required five valid observations per configuration
and passed the mandatory 5% median-error gate. SCIP `presolve-off` exceeded the
preferred, non-binding 10% CV target; the matrix remains accepted, but this
deviation must accompany interpretation of that profile.

The SCIP default/instance-15 cell initially retained four valid attempts.
Two independent attempts were then collected in a separate output root under
the same contract. Both passed telemetry validation. A deterministic compositor
replaced the two invalid run positions in chronological order, without using
solver outcome, energy, duration, objective, bound, gap, or node count. The
original matrix, retry files, and checksummed composition manifest remain
preserved. Consequently, 362 physical attempts produced a 360-row logical
matrix; the composed evidence still reports the remaining invalid observations.

## Controlled paired comparison

The corrected comparator accepted both matrices, verified effective
minimization and the 300-second budget, and classified the result as
`controlled-comparison`. All comparison gates passed: the one-core
configurations are complete; dataset fingerprints, profile contracts, objective
direction, time budget, partition, and exclusive-allocation evidence match; the
source worktrees are clean; and both input matrices are accepted.

| Profile | Median duration ratio | Median energy ratio | Median EDP ratio |
| --- | ---: | ---: | ---: |
| Default | 1.069927 | 0.995437 | 1.064858 |
| Presolve off | 1.011974 | 0.958652 | 0.970521 |
| Warm start | 1.072602 | 1.000150 | 1.072563 |

Ratios are SCIP divided by Gurobi and are medians over the five paired
instance-level ratios for each profile. The accepted report is
`dual_solver_comparison.json`, SHA-256
`a799ed44b0be5001ac71ca0b1ef59bc3269f369a554235ae92509d7876b425f8`.
Its companion `solver_measurements.csv` and
`paired_one_core_comparisons.csv` files have SHA-256 values
`68b8395d2ce4656e72099e673e5a5ab36d0c1b081347cb3934fcd94503b8069b`
and
`9a6d1bf09cf8091ca4f80c230eb72c1a06dd602d7e5f4a542262d41909dc328d`,
respectively.

The final values apply only to the declared CFL instances, solver versions,
profiles, one-core comparison, and NPAD execution conditions. Time-limited runs
describe fixed-budget progress and energy, not time to proven optimality. Native
sentinel values such as SCIP `-1e20` and `1e20` are unavailable bound/gap
indicators and must not be interpreted as scientific measurements.

## Evidence handling

Raw telemetry, warm-start files, and cluster logs remain outside Git. The
comparison tool creates checksummed JSON and CSV reports. The portable evidence
exporter verifies those reports and the two accepted input matrices, replaces
cluster-local paths with logical artifact names, and emits a deterministic
`evidence_manifest.json` with its own `SHA256SUMS` file.

This separation keeps the repository lightweight while retaining a verifiable
chain from source commit and experiment configuration to the reported result.

