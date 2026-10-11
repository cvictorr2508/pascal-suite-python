# Research context

## Research stream

PaScal Suite Python is the energy-telemetry and reproducibility stream of a
larger postdoctoral research portfolio. It must remain scientifically and
operationally independent from the agrologistics and CFL-GNN streams. Shared
ideas may be discussed across projects, but code, evidence, claims, and
manuscript decisions belong to their respective repositories.

The software connects solver-native Python APIs to PaScal Analyzer on an HPC
system. Its central contribution is an auditable workflow for attributing
runtime and energy to model-loading and solve-execution regions while retaining
solver, experiment, scheduler, dataset, and source provenance.

## Scientific objective

The bounded objective is to determine whether a solver-neutral Python workflow
can produce reproducible regional time-and-energy measurements for mathematical
optimization experiments in the evaluated NPAD environment.

The validated study addresses four questions:

1. Can Gurobi and SCIP use one declarative experiment contract while preserving
   solver-specific semantics?
2. Does integrated sampled RAPL power agree with a separately acquired global
   RAPL reading within the predefined internal-consistency threshold?
3. Do accepted configurations retain sufficient valid replication and
   preferred repeatability after invalid telemetry is rejected?
4. Under matched one-core, partition, allocation, profile, dataset, objective,
   and time-budget conditions, how do duration, regional energy, and EDP differ
   descriptively between the solvers?

These questions do not imply universal solver superiority, absolute
power-meter accuracy, or time to proven optimality.

## Validated system boundary

- Solvers: Gurobi and SCIP.
- Workloads: MILPBench hard capacitated facility-location instances 5, 10, 15,
  20, and 25.
- Profiles: `default`, `presolve-off`, and `warm-start`.
- Instrumentation: PaScal Analyzer with global RAPL energy and sampled RAPL
  power.
- Regions: complete pipeline (`0`), model import (`0.1`), and solve execution
  (`0.2`).
- Environment: the recorded NPAD Slurm allocation and software versions.

PaScal Viewer support for regional-energy visualization was integrated through
[GitLab MR !15](https://gitlab.com/lappsufrn/pascalsuite-viewer/-/merge_requests/15)
and is publicly accessible from the
[PaScal Viewer landing page](https://pascalsuite.imd.ufrn.br/viewer/).

## Source-of-truth hierarchy

When sources disagree, use this order:

1. immutable raw evidence, manifests, and checksums in the external evidence
   store;
2. accepted machine-readable summaries and the published Zenodo dataset;
3. experiment contracts and validation code at the recorded source commit;
4. reviewed repository documentation and the Quarto manuscript;
5. `docs/current_status.md` as an operational index;
6. chat summaries and local notes as non-authoritative context.

Large evidence remains outside Git. The repository stores the code, contracts,
processed publication data, documentation, and persistent identifiers needed
to reconstruct the evidence chain.

### Generation-aware interpretation

The October 10 audit identified coexistence of historical source-sense results
and corrected explicit-minimization/300-second results. Do not treat the
unqualified path `publication/results/` as proof of the current generation.
Resolve a result's generation, campaign source commit, contract, and checksum
before citing it. The software release commit and campaign execution commit
are separate identifiers.

An accepted processed-result gate does not certify complete distributed raw
provenance. The corrected dataset has pending outer-PNG checksum, retry-chain,
and sanitization documentation issues. Preserve published evidence and record
these gaps rather than silently repairing it or inferring a numerical error
in the submitted manuscript.

## Public research objects

- Software concept DOI: <https://doi.org/10.5281/zenodo.22695373>.
- Software version 0.2.0 DOI: <https://doi.org/10.5281/zenodo.23082727>.
- Dataset concept DOI: <https://doi.org/10.5281/zenodo.22709482>.
- Corrected dataset version 2.0.0: <https://zenodo.org/records/23071850>.
- Public Quarto manuscript: <https://cvictorr2508.github.io/pascal-suite-python/>.
- Source repository: <https://github.com/cvictorr2508/pascal-suite-python>.

The submitted article and its response-to-review history are publication
records. They must not be treated as interchangeable with the live Quarto page
after submission.
