# Dual-solver research MVP validation

## Scope

This document records the bounded validation of the PaScal Suite Python
dual-solver research MVP. The experiment compares Gurobi and SCIP on five
MILPBench CFL hard instances under three solver profiles. It is a reproducible
demonstration in a relevant HPC environment, not a universal solver benchmark.

## Experimental contract

- Workloads: `CFL_hard_instance_{5,10,15,20,25}.lp.gz`.
- Profiles: `default`, `presolve-off`, and `warm-start`.
- Repetitions: six attempts per configuration.
- Comparison resource: one solver core.
- Telemetry: PaScal Analyzer `2025-07-08`, global RAPL energy, and sampled RAPL
  power.
- Compared region: `0.2`, the solve-execution interval.
- Scheduler: NPAD `intel-128`, explicit exclusive allocation, and Slurm
  `OverSubscribe=NO` for both campaigns.
- Required accuracy: median absolute regional-energy error at most 5%.
- Preferred repeatability: maximum configuration-level region-0 CV at most 10%.
- Replication gate: at least five valid runs per configuration.

Invalid RAPL attempts were reported and excluded. No value was corrected,
replaced, or imputed.

## Accepted campaigns

### Gurobi

- Slurm job: `2084725`.
- Source commit: `915bd7974edf2a03a279d24a0e3a69dc5f54082f`.
- Partition and policy: `intel-128`, requested `exclusive`, observed
  `OverSubscribe=NO`.
- Resource treatments: 1, 2, and 4 solver cores.
- Default: 88/90 valid attempts; median error 0.201043%; maximum CV 1.450886%.
- Presolve off: 89/90 valid; median error 0.290858%; maximum CV 1.877484%.
- Warm start: 90/90 valid; median error 0.268701%; maximum CV 1.124702%.

All 15 Gurobi configurations passed.

### SCIP

- Slurm job: `2084503`.
- Source commit: `b03b6f298db70834192fb499f8fd248e91de22e9`.
- Partition and policy: `intel-128`, requested `exclusive`, observed
  `OverSubscribe=NO`.
- Resource treatment: one solver core.
- Default: 29/30 valid attempts; median error 0.296794%; maximum CV 1.654691%.
- Presolve off: 30/30 valid; median error 0.286874%; maximum CV 0.671986%.
- Warm start: 28/30 valid; median error 0.290148%; maximum CV 0.746351%.

All five configurations in each SCIP profile passed.

## Controlled paired comparison

Dataset fingerprints, profile contracts, source cleanliness, allocation policy,
and hardware partition matched. The comparator accepted 15 paired one-core
configurations and classified the result as `controlled-comparison`.

The values below are medians of the per-instance SCIP/Gurobi ratios. Values
greater than one indicate a larger SCIP measurement.

| Profile | Duration ratio | Energy ratio | EDP ratio |
| --- | ---: | ---: | ---: |
| Default | 26.314715 | 26.794993 | 707.638806 |
| Presolve off | 43.115530 | 43.876481 | 1893.048508 |
| Warm start | 9.775579 | 10.186012 | 99.737732 |

These results apply only to the declared CFL instances, solver versions,
profiles, one-core comparison, and NPAD execution conditions. In particular,
they must not be presented as solver-wide superiority claims.

## Evidence handling

Raw telemetry, warm-start files, and cluster logs remain outside Git. The
comparison tool creates checksummed JSON and CSV reports. The portable evidence
exporter verifies those reports and the two accepted input matrices, replaces
cluster-local paths with logical artifact names, and emits a deterministic
`evidence_manifest.json` with its own `SHA256SUMS` file.

This separation keeps the repository lightweight while retaining a verifiable
chain from source commit and experiment configuration to the reported result.

