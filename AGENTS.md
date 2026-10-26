# Repository guidance for coding agents

## Purpose

This repository is the portable operational memory for the PaScal Suite Python
research stream. Keep this work scientifically independent from the
agrologistics and CFL-GNN projects, which have their own repositories,
experiments, and manuscripts.

Before changing code, experiments, documentation, or the manuscript, read:

1. `docs/research_context.md` for the scientific scope and source-of-truth
   hierarchy;
2. `docs/current_status.md` for the latest accepted state and restart triggers;
3. `docs/experiment_protocol.md` for experimental invariants and evidence
   rules;
4. `docs/article_plan.md` for the submission and peer-review workflow;
5. the narrower implementation document relevant to the requested change.

## Current operating authorization

The author authorized autonomous development in the user's Codex area and on
GitHub on 26 October 2026, including branch, commit and PR preparation. Request
explicit approval before every merge and every NPAD execution. This does not
turn a proposed scientific protocol into an executed or validated result.

- Store any local development artifacts under `C:\Users\cvict\.codex`, not in
  the OneDrive `Temp Codex/pascal-suite-python` directory or the old source clone.
- Keep private correspondence and reviewer text outside the public repository.
- Do not create anything under `/home/vrrcelestino` on NPAD, including code,
  worktrees, evidence, temporary files, caches, logs and generated manifests.
- Before requesting NPAD execution approval, specify exact authorized code,
  evidence, scratch/cache and log roots outside that prohibited path, commands,
  resource limits and outputs. Include implicit Python, solver, build and Slurm
  outputs in the path review. Do not run remote probes before approval.
- Directory names in a screenshot and historical checkpoint paths do not
  establish approved absolute destinations. Do not invent their parent paths.

## Branch and publication policy

- Use a narrowly scoped branch and pull request for every change.
- Use `develop` as the integration target for ongoing research planning and
  implementation unless the user explicitly selects another base.
- Treat `main` as the reviewed public software, documentation, and GitHub Pages
  state. Do not merge or push directly to `main`.
- Do not promote research-memory documents from `develop` to `main` without an
  explicit decision that they are suitable for the public repository.
- Preserve submitted manuscript files and published Zenodo records as immutable
  artifacts. Corrections require a new revision or version, never overwriting.

## Scientific invariants

- The reported capacitated facility-location experiments use explicit
  minimization after native model import. Record both source and effective
  objective directions.
- The corrected controlled campaigns use a 300-second solver budget, six
  attempts per configuration, and at least five telemetry-valid attempts.
- Distinguish `TIME_LIMIT` from `OPTIMAL`. Fixed-budget results are not time to
  proven optimality and do not establish universal solver rankings.
- Never repair, impute, or select measurements using objective value, bound,
  gap, duration, energy, EDP, or solver outcome.
- A selective retry is allowed only for a failed telemetry-replication cell,
  under the same scientific contract and in a separate immutable output root.
- Local workload reindexing must not silently change the effective seed.
  Verify retry parameter equivalence separately from telemetry validity.
- Treat the 5% median energy-consistency threshold as mandatory and the 10%
  configuration CV threshold as preferred and non-binding, with exceedances
  disclosed.

## HPC and evidence rules

- The workflow is repository to HPC to external evidence storage to reviewed
  publication artifacts. Do not require cloud access from compute nodes.
- Keep benchmark archives, raw telemetry, solver licenses, large start files,
  and cluster logs out of Git.
- Commit experiment contracts, scripts, checksums, manifests, compact processed
  results, and stable references to external artifacts.
- Use the activated Python 3.13 environment on NPAD. Do not invent environment
  paths or substitute a login-node hardware inventory for compute-node
  provenance.
- Keep Slurm and shell files in Unix LF format. Avoid shell-level `exit 1` in
  interactive VS Code terminal snippets because it can close the terminal.
- Never overwrite accepted campaign roots. Diagnose and retry only the exact
  failed unit in a separate directory.

## Validation and communication

- Run tests, focused linting, bibliography provenance, Quarto rendering, and
  PDF checks in proportion to the changed files.
- Report unavailable tools or environment limitations instead of weakening a
  gate.
- Use English for repository documentation, code comments, commit messages, and
  pull-request text.
- Update `docs/current_status.md` only with verified outcomes. Mark assumptions,
  pending decisions, and externally executed steps explicitly.
- Keep commands reproducible and non-destructive. Ask before publishing,
  releasing, merging, deleting evidence, cancelling jobs, or changing a
  scientific acceptance rule.
- Resolve the experimental generation before using a processed result. Never
  replace historical CSVs with corrected values under the same identifier.
- Distinguish numerical consistency, telemetry validity, and completeness of
  the distributed physical provenance chain. Do not mark missing retry records
  verified merely because the logical matrix gate passed.
