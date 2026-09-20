InvalidOperation: 
Line |
   2 |  [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); Ge .
     |  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
     | Cannot create type. Only core types are supported in this language mode.
# Gurobi hard-instance default-profile revalidation

This campaign measures the five selected MILPBench capacitated facility-location
instances after correcting their objective direction from the source-file
maximization declaration to the intended minimization problem. A controlled
smoke run on instance 20 reached the 300-second limit with a 98.82% gap, proving
that the corrected problem is nontrivial. The campaign records termination,
incumbent, best bound, MIP gap, model dimensions, regional energy, and
provenance.

## Fixed contract

- solver: Gurobi;
- objective direction: explicitly forced to minimization after `gp.read()`;
- algorithmic profile: defaults apart from the existing runner-controlled
  `Threads` and deterministic `Seed=10000+input_index` settings;
- sole profile parameter: `TimeLimit=300` seconds;
- workloads: hard instances 5, 10, 15, 20, and 25 in that order;
- PaScal resources and Gurobi `Threads`: 1, 2, and 4;
- repetitions: six per configuration;
- telemetry: global and sampled `rapl-sysfs` with regions 0, 0.1, and 0.2;
- allocation: one exclusive `intel-128` node per shard;
- matrix: 15 shards, each containing six attempts for one instance/thread pair.

The solver budget is 30 minutes per shard in the worst case. The Slurm default
is one hour, leaving approximately 30 minutes for six model loads,
instrumentation, serialization, and shutdown. The complete matrix contains 7.5
node-hours of solver budget. The launcher limits the array to three concurrent
exclusive nodes by default, producing five scheduling waves. Override
concurrency only after reviewing cluster policy and availability.

The label `default` means the same default profile used by the published
pipeline, subject to its explicit minimization direction, thread count,
deterministic seed, and the 300-second termination budget. The resulting
campaign must not be described as having an unlimited or completely untouched
Gurobi-default run. `TimeLimit` is a maximum budget, not a minimum execution
duration: a proof of optimality may still terminate early and must be interpreted
using status, bound, and gap.

## Objective-sense validity correction

The supplied LP files declare a maximization objective, while the capacitated
facility-location experiment is a minimization problem. Preserving the file
direction makes the instances trivial: Gurobi accepts a heuristic solution and
proves it optimal at the root without simplex or branch-and-bound iterations.
Those maximization runs, including campaign `2107909`, are retained only as
invalidated audit evidence and must not be used in scientific results.

The corrected profile declares `objective_sense: minimize`. After `gp.read()`,
the runner records the source direction and model fingerprint, assigns
`model.ModelSense = GRB.MINIMIZE`, updates the model, and records the effective
direction and fingerprint before entering region 0.2. The campaign summarizer
fails closed unless every attempt proves that minimization was requested and
effective. This explicit transformation is part of the experimental treatment,
not a Gurobi algorithmic parameter.

## Why the campaign is sharded

A single Analyzer matrix contains 90 attempts and would execute serially for at
least 7.5 hours of optimization alone. Sharding by configuration bounds each
job to six 300-second attempts, allows a failed cell to be retried without
overwriting accepted evidence, and preserves the six attempts inside one PaScal
batch.

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
- `gurobi_hard_default_300s_viewer.json`, a compact Viewer artifact containing
  exact validated regional-energy integrals but not the large raw power series.

The compact file contains only attempts that pass the fail-closed energy checks.
Rejected attempts and reasons remain in `campaign_summary.json`; raw evidence is
never deleted or overwritten by the summarizer.

