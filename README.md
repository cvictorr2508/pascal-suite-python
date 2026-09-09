# PaScal Suite Python

PaScal Suite Python is a research-oriented wrapper for reproducible experiments
with mathematical optimization solvers and the
[PaScal Analyzer](https://pascalsuite.imd.ufrn.br/analyzer/) on HPC systems. It
currently supports Gurobi and SCIP through a shared, file-based experiment
contract and has been evaluated on the NPAD cluster at the Federal University
of Rio Grande do Norte (UFRN).

The software is an experimental research prototype, not a production service.
Its purpose is to make solver execution, regional energy measurement, scheduler
conditions, and evidence provenance explicit and auditable.

## Research objective and questions

The primary objective is to evaluate whether a solver-neutral Python workflow
can produce reproducible time-and-energy measurements for mathematical
optimization experiments in a relevant HPC environment.

The current implementation addresses four bounded research questions:

- **RQ1 — Execution parity:** Can Gurobi and SCIP be executed through the same
  declarative experiment contract while retaining solver-specific semantics?
- **RQ2 — Energy consistency:** Does energy obtained by integrating sampled RAPL
  power agree with the independent global RAPL measurement within the predefined
  5% median absolute-error threshold?
- **RQ3 — Repeatability:** Does each accepted configuration remain within the
  preferred 10% coefficient-of-variation threshold after invalid measurements
  are rejected?
- **RQ4 — Controlled comparison:** Under matched dataset, profile, allocation,
  partition, and one-core conditions, how do observed solve duration, regional
  energy, and energy-delay product (EDP) differ between the two solvers?

These questions concern the validated experimental configuration. They do not
imply solver-wide performance rankings.

## Research scope and maturity

The current MVP demonstrates the complete workflow in a relevant HPC
environment:

- declarative experiment matrices for Gurobi and SCIP;
- solver profiles for `default`, `presolve-off`, and `warm-start`;
- hierarchical regions for the complete pipeline, model loading, and solve
  execution;
- native global RAPL energy and sampled RAPL power from PaScal Analyzer;
- regional energy integration with explicit rejection of invalid samples;
- source, dataset, runtime, configuration, warm-start, and Slurm provenance;
- fail-closed gates for accuracy, repeatability, replication, allocation policy,
  hardware partition, and dataset identity;
- deterministic solver comparison and portable evidence manifests.

This evidence supports a TRL 5 research prototype and a bounded TRL 6
demonstration of the validated end-to-end workflow. TRL interpretation is
limited to technical operation in the NPAD environment; it is not a claim of
production readiness, operational deployment, or broad scientific
generalization.

## Experimental design

The experimental unit is one solver attempt for a specific workload, solver
profile, and solver-core treatment. The validated hard-instance campaigns use:

| Design element | Operationalization |
| --- | --- |
| Solvers | Gurobi and SCIP |
| Workloads | MILPBench CFL hard instances 5, 10, 15, 20, and 25 |
| Profiles | `default`, `presolve-off`, and `warm-start` |
| Attempts | Six per configuration, with at least five valid attempts required |
| Core treatments | Gurobi: 1, 2, and 4; SCIP comparison: 1 |
| Comparison region | `0.2`, solve execution |
| Responses | duration, energy, and EDP |
| Measurement controls | identical workload hashes, matched profile contract, clean source worktrees, the same Slurm partition, and exclusive allocation |

The profile matrix summarizer reports attempted and valid observations
separately. Invalid RAPL power or energy observations are disclosed and
excluded without correction or imputation. Accuracy is evaluated by comparing
sampled whole-program energy with the independent global RAPL value. Regional
energy is then derived only for runs whose sampled series passes the validity
checks.

The study uses medians and coefficients of variation as descriptive statistics.
It does not currently report confidence intervals, hypothesis tests, or
population-level effect estimates.

## Architecture

The pipeline has four layers:

1. A YAML document declares the solver, workloads, resource treatments,
   repetitions, profiles, telemetry policy, and output directory.
2. A solver-neutral adapter builds a PaScal Analyzer batch around a native ELF
   region proxy. The Analyzer remains the authoritative source of telemetry.
3. A solver runner loads the model, applies the selected profile, executes the
   optimization, and writes per-attempt metadata.
4. Validation tools consolidate regional energy, reject invalid attempts,
   compare accepted matrices, and export checksummed evidence.

The runners expose the same hierarchical region contract:

| Region | Meaning |
| --- | --- |
| `0` | Complete solver pipeline |
| `0.1` | Model read/build phase |
| `0.2` | Solve execution |

The native proxy is required because the PaScal build evaluated at NPAD records
manual regions only when the instrumentation calls originate from the native
process launched by the Analyzer. Python communicates region boundaries to that
process over a guarded IPC protocol; it does not rewrite the Analyzer JSON.

## Repository layout

- `src/pascalpy/`: library code, solver adapters, runners, profiles, and
  instrumentation.
- `experiments/`: reproducible Gurobi and SCIP experiment contracts.
- `jobs/`: Slurm launchers, including allocation-policy capture.
- `scripts/`: validation, comparison, warm-start, and evidence tools.
- `tests/`: unit and regression tests.
- `docs/`: architecture decisions and NPAD validation records.
- `instances/`: small public fixtures only.
- `resultados_finais/`: generated telemetry and reports; intentionally ignored
  by Git.

## Requirements and installation

Python 3.13 is required. PaScal Analyzer and its native instrumentation library
must be provided by the HPC environment.

Install the core package and the solver required for an experiment:

```bash
python -m pip install -e '.[gurobi]'
python -m pip install -e '.[scip]'
```

For the complete research and analysis environment:

```bash
python -m pip install -e '.[research,dev]'
```

Gurobi additionally requires a valid license. The reproducible launcher expects
it at `secret/gurobi.lic` unless `GRB_LICENSE_FILE` selects another location.
SCIP experiments use PySCIPOpt and do not require a separate `scip` executable.

## Solver profiles

Both solvers implement the same operational profile contract:

- `default`: solver defaults plus the controlled resource and seed settings;
- `presolve-off`: presolve is explicitly disabled and the effective setting is
  recorded;
- `warm-start`: a required initial solution is loaded and its acceptance is
  recorded.

Gurobi warm starts may use `.mst`, `.sol`, or a JSON variable map. SCIP warm
starts use `.sol` or `.sol.gz`. The contract aligns experimental intent, but
the solver-native representations and acceptance mechanisms are not presumed
to be algorithmically identical. Large generated warm-start files and raw
telemetry must remain outside Git.

## Running an experiment on Slurm

Activate the intended Python environment before submission. The launcher
captures the active Python executable and Git provenance, rejects tracked local
changes, and passes that immutable submission context into Slurm.

```bash
PASCAL_SLURM_ALLOCATION_MODE=exclusive \
bash jobs/submit_solver_experiment.sh \
    experiments/gurobi-hard-profiles.yaml
```

Use `experiments/scip-hard-profiles.yaml` for SCIP. Evidence intended for
controlled performance comparison requires `exclusive`; `shared` exists only
for diagnostic runs and is recorded as such. Slurm scripts use Unix LF line
endings.

The hard-profile contracts refer to five MILPBench CFL instances: IDs 5, 10,
15, 20, and 25. Dataset files are not committed. Verify their location and
fingerprints before submission.

## Validating a profile matrix

After a successful job, consolidate each solver matrix:

```bash
python scripts/summarize_solver_profile_matrix.py \
    resultados_finais/gurobi_hard_profiles \
    --require-runs 5 \
    --require-configurations 15

python scripts/summarize_solver_profile_matrix.py \
    resultados_finais/scip_hard_profiles \
    --require-runs 5 \
    --require-configurations 5
```

The mandatory energy-consistency criterion is a median absolute error no
greater than 5% for sampled whole-program energy relative to global RAPL energy.
A maximum configuration-level coefficient of variation no greater than 10% is
the preferred repeatability criterion. Every configuration must retain at least
five valid attempts.

## Controlled Gurobi–SCIP comparison

Build the comparison only from accepted matrices:

```bash
python scripts/compare_solver_profile_matrices.py \
    --gurobi-root resultados_finais/gurobi_hard_profiles \
    --scip-root resultados_finais/scip_hard_profiles \
    --output-dir resultados_finais/dual_solver_research_mvp
```

The comparison is eligible for a controlled performance claim only when both
campaigns:

- record clean source worktrees;
- use identical workload fingerprints and profile contracts;
- explicitly request exclusive allocation;
- record `OverSubscribe=NO` from Slurm;
- run on the same non-empty partition.

Otherwise, the tool still writes auditable outputs but labels them
`exploratory-only`, rejects the final gate, and returns status 3.

The accepted campaign and its bounded descriptive results are documented in
[Dual-solver research MVP validation](docs/research-mvp.md).

## Evidence and data availability

Raw PaScal telemetry can be large and may contain cluster-local paths. Export a
small, deterministic evidence package after an accepted controlled comparison:

```bash
python scripts/export_research_evidence.py \
    --gurobi-root resultados_finais/gurobi_hard_profiles \
    --scip-root resultados_finais/scip_hard_profiles \
    --comparison-root resultados_finais/dual_solver_research_mvp \
    --output-dir resultados_finais/dual_solver_research_mvp/portable_evidence
```

The exporter verifies upstream hashes and gates, strips absolute paths, records
logical artifact names and checksums, and produces `evidence_manifest.json`
plus `SHA256SUMS`. Raw campaigns should be retained in external immutable
storage, while the portable manifest can accompany a research report.

The benchmark datasets are distributed by MILPBench and are intentionally not
versioned here:

- [CFL easy](https://drive.google.com/file/d/1z6oNG1ja6CwlsRYViXIzBj0j8Ch6sxdt/view?usp=sharing)
- [CFL medium](https://drive.google.com/file/d/181Evo5Q6otZRq6EBeQXFcCYlC4kM8zaH/view?usp=sharing)
- [CFL hard](https://drive.google.com/file/d/13NS9YTTyNsiV6Dth3qsQ7lWWNQs4Pek0/view?usp=sharing)

## Threats to validity

- **External validity:** the current evidence covers one benchmark family, five
  instances, one HPC system, one CPU partition, and the recorded solver and
  PaScal versions.
- **Internal validity:** exclusive allocation, partition matching, provenance,
  and workload hashes reduce confounding, but campaigns executed as separate
  jobs may still experience node-level and temporal variation.
- **Construct validity:** RAPL estimates CPU/package energy rather than complete
  facility or system energy. No carbon-emissions claim is made. EDP refers to
  the declared measurement region and telemetry domain.
- **Statistical conclusion validity:** six attempts per configuration provide
  redundancy for invalid telemetry but limited inferential power. Reported
  medians, ratios, and coefficients of variation are descriptive.
- **Treatment equivalence:** profile names express matched experimental intent;
  solver defaults, presolve implementations, and warm-start handling remain
  solver specific.

These limitations must accompany any interpretation or publication of the
results.

## PaScal Viewer

The wrapper requests both global energy (`--rple`) and sampled RAPL power
(`--rpls`). The PaScal Viewer integrates the sampled series over the union of
region intervals and displays Energy and EDP without modifying the uploaded
JSON. Viewer integration is maintained in a separate repository.

## Testing

```bash
python -m pytest -q
```

Generated results, licenses, virtual environments, build products, and solver
warm starts must not be committed.
