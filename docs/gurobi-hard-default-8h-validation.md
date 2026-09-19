# Gurobi hard-instance default-profile revalidation

This campaign re-examines the unexpectedly short solve-region durations reported
for the five selected MILPBench capacitated facility-location instances. It does
not assume that the `hard` label guarantees an eight-hour solve. Instead, it
records whether each run terminates optimally or reaches the declared solver
limit, together with incumbent, best bound, MIP gap, model dimensions, regional
energy, and provenance.

## Fixed contract

- solver: Gurobi;
- algorithmic profile: defaults apart from the existing runner-controlled
  `Threads` and deterministic `Seed=10000+input_index` settings;
- sole profile parameter: `TimeLimit=28800` seconds;
- workloads: hard instances 5, 10, 15, 20, and 25 in that order;
- PaScal resources and Gurobi `Threads`: 1, 2, and 4;
- repetitions: six per configuration;
- telemetry: global and sampled `rapl-sysfs` with regions 0, 0.1, and 0.2;
- allocation: one exclusive `intel-128` node per shard;
- matrix: 15 shards, each containing six attempts for one instance/thread pair.

The solver budget is 48 hours per shard in the worst case. The Slurm default is
52 hours, leaving four hours for six model loads, instrumentation, serialization,
and shutdown. The submission launcher limits the array to three concurrent
exclusive nodes by default. Override concurrency only after reviewing cluster
policy and availability.

The label `default` means the same default profile used by the published
pipeline, subject to its explicit thread count, deterministic seed, and the new
eight-hour termination budget. The resulting campaign must not be described as
having an unlimited or completely untouched Gurobi-default run. `TimeLimit` is
a maximum budget, not a minimum execution duration: a proof of optimality may
still terminate in seconds and must be interpreted using status, bound, and gap.

## Why the campaign is sharded

A single Analyzer matrix contains 90 attempts. If every attempt reaches eight
hours, the job would require 720 hours, exceeding the known partition limit.
Sharding by configuration keeps each job bounded, allows a failed cell to be
retried without overwriting accepted evidence, and preserves the six attempts
inside one PaScal batch.

Different shards may execute on different nodes. The output is suitable for the
requested descriptive heatmap and termination audit, but node identity must be
retained and cross-configuration differences must not be presented as a strict
causal scaling comparison unless node effects are separately controlled.

## Outputs

Raw Analyzer JSON and power samples remain under `shards/c<cores>_i<input>/`.
After all 15 shards complete, the summarizer validates the energy series and
creates:

- `campaign_summary.json`, including statuses, runtime, bounds, gaps, energy
  consistency, hashes, and shard provenance;
- `gurobi_hard_default_8h_viewer.json`, a compact Viewer artifact containing
  exact validated regional-energy integrals but not the large raw power series.

The compact file contains only attempts that pass the fail-closed energy checks.
Rejected attempts and reasons remain in `campaign_summary.json`; raw evidence is
never deleted or overwritten by the summarizer.
