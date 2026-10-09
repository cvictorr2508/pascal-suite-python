# Corrected experiment protocol

## Purpose

This document records the invariant protocol behind the accepted WPADS 2026
evidence. It is a restart guide, not authorization to launch a new campaign.
See `docs/research-mvp.md` for the accepted numerical results and evidence
hashes.

## Experimental design

| Element | Contract |
| --- | --- |
| Solvers | Gurobi and SCIP |
| Workloads | MILPBench CFL hard instances 5, 10, 15, 20, and 25 |
| Objective | Explicit minimization, verified after native model import |
| Profiles | `default`, `presolve-off`, and `warm-start` |
| Solver budget | 300 seconds per attempt |
| Attempts | Six per configuration |
| Valid replication | At least five telemetry-valid attempts per configuration |
| Gurobi treatments | 1, 2, and 4 cores/threads |
| SCIP comparison | 1 core |
| Scheduler control | Same recorded NPAD partition and exclusive allocation |
| Comparison region | Region `0.2`, solve execution |
| Responses | Duration, regional energy, and EDP |

The LP inputs declare maximization, but the intended capacitated
facility-location experiment is minimization. Each runner must capture the
source objective sense, force minimization, verify the effective sense, and
write those values to per-attempt metadata before optimization.

## Telemetry and regions

- Region `0` covers the complete solver pipeline.
- Region `0.1` covers native model import/loading, not algebraic model
  generation.
- Region `0.2` covers solver optimization.
- Profile configuration and start-file loading occur inside region `0` but
  outside child regions `0.1` and `0.2`.
- Sampled RAPL power is integrated only after fail-closed validity checks.
- Integrated whole-program energy is compared with separately acquired global
  RAPL energy to assess internal consistency, not absolute sensor accuracy.

## Acceptance rules

1. Preserve attempted and valid counts separately.
2. Reject invalid power, energy, coverage, or metadata observations without
   correction or imputation.
3. Require at least five valid attempts in every configuration.
4. Require median absolute energy-consistency error at most 5%.
5. Report the maximum configuration-level region-0 CV. The preferred threshold
   is 10%; an exceedance is disclosed but is not by itself a mandatory failure.
6. Require matching dataset fingerprints, profile contract, objective sense,
   solver budget, partition, allocation policy, and clean source provenance for
   controlled comparison.
7. Interpret native sentinel bounds or gaps as unavailable data, not scientific
   measurements.

## Retry and composition policy

A selective retry is permitted only when independent telemetry invalidity
leaves a configuration below the replication requirement. The retry must:

- use the same source commit and scientific contract;
- use the same workload, solver profile, resource treatment, partition, and
  allocation mode;
- write to a separate output root;
- be selected chronologically using telemetry validity only;
- preserve original, retry, and composed evidence with a checksummed
  composition manifest.

Never select a retry by solver status, objective, bound, gap, node count,
duration, energy, or EDP. Never overwrite the original matrix.

## Reproducible execution sequence

1. Verify the intended source commit, clean tracked worktree, Python 3.13
   environment, solver versions, license availability, workload fingerprints,
   warm starts, LF line endings, and external output root.
2. Submit through the repository launcher with explicit allocation policy.
3. Preserve `sacct`, stdout, stderr, research manifests, Analyzer JSON, and
   per-attempt metadata.
4. Run matrix summarization with the declared replication and configuration
   counts.
5. If needed, retry only a failed telemetry cell under the policy above.
6. Run the controlled comparison and require every mandatory gate to pass.
7. Generate SHA-256 manifests before moving, packaging, or publishing evidence.
8. Export only a sanitized derivative after manual privacy, authorship, file,
   and hardware-documentation review.

Large evidence belongs in the external evidence store or Zenodo, not Git. Git
retains the executable contract and compact processed publication results.

## Reporting boundary

Time-limited runs report fixed-budget progress and energy. They are not time to
proven optimality. Ratios are descriptive for the declared instances, versions,
profiles, one-core comparison, and NPAD conditions. They must not be generalized
to solver-wide rankings without a new study and statistical design.
