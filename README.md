# PaScal Suite Python

PaScal Suite Python is a research-oriented wrapper for reproducible experiments
with mathematical optimization solvers and the
[PaScal Analyzer](https://pascalsuite.imd.ufrn.br/analyzer/) on HPC systems. It
currently supports Gurobi and SCIP through a shared, file-based experiment
contract and was validated on the NPAD cluster at the Federal University of Rio
Grande do Norte (UFRN).

The project is an experimental research MVP, not a production service. Its goal
is to provide auditable solver experiments, native PaScal telemetry, regional
energy estimates, and controlled solver comparisons under explicitly recorded
scheduler conditions.

## Research scope and maturity

The current MVP demonstrates the complete workflow in a relevant HPC
environment:

- declarative experiment matrices for Gurobi and SCIP;
- solver profiles for `default`, `presolve-off`, and `warm-start`;
- hierarchical regions for the full pipeline, model construction, and solve;
- native global RAPL energy and sampled RAPL power from PaScal Analyzer;
- regional energy integration with explicit rejection of invalid samples;
- source, dataset, runtime, configuration, warm-start, and Slurm provenance;
- fail-closed scientific gates for accuracy, variability, replication,
  allocation policy, hardware partition, and dataset identity;
- deterministic comparison and portable evidence manifests.

This supports a TRL 5 research MVP and a bounded TRL 6 demonstration for the
validated workflow. It does not establish universal performance claims across
different hardware, datasets, solver versions, or parameter spaces.

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

The native proxy is required because the PaScal build validated at NPAD records
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

## Experiment profiles

Both solvers implement the same three profile semantics:

- `default`: solver defaults plus the controlled resource and seed settings;
- `presolve-off`: presolve is explicitly disabled and the effective setting is
  recorded;
- `warm-start`: a required initial solution is loaded and its acceptance is
  recorded.

Gurobi warm starts may use `.mst`, `.sol`, or a JSON variable map. SCIP warm
starts use `.sol` or `.sol.gz`. Large generated warm-start files and raw
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

Use `experiments/scip-hard-profiles.yaml` for SCIP. Production evidence requires
`exclusive`; `shared` exists only for diagnostic runs and is recorded as such.
The Slurm scripts use Unix LF line endings.

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

The mandatory regional-energy accuracy criterion is a median absolute error no
greater than 5% against independent global RAPL energy. A maximum coefficient
of variation no greater than 10% is the preferred repeatability criterion.
Invalid power or energy attempts are reported and excluded; they are never
corrected or imputed. Every configuration must retain at least five valid runs.

## Controlled Gurobi-SCIP comparison

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

## Portable evidence

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
plus `SHA256SUMS`. Keep the raw campaigns in external immutable storage and
publish the portable manifest alongside any research report.

## PaScal Viewer

The wrapper requests both global energy (`--rple`) and sampled RAPL power
(`--rpls`). The PaScal Viewer integrates the sampled series over the union of
region intervals and displays Energy and EDP without modifying the uploaded
JSON. The Viewer integration is maintained in its separate repository.

## Dataset access

The benchmark datasets are distributed by MILPBench and are intentionally not
versioned here:

- [CFL easy](https://drive.google.com/file/d/1z6oNG1ja6CwlsRYViXIzBj0j8Ch6sxdt/view?usp=sharing)
- [CFL medium](https://drive.google.com/file/d/181Evo5Q6otZRq6EBeQXFcCYlC4kM8zaH/view?usp=sharing)
- [CFL hard](https://drive.google.com/file/d/13NS9YTTyNsiV6Dth3qsQ7lWWNQs4Pek0/view?usp=sharing)

## Testing

```bash
python -m pytest -q
```

Generated results, licenses, virtual environments, build products, and solver
warm starts must not be committed.

