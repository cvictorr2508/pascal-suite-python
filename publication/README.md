# Publication data and results

This directory contains the compact, machine-readable results reported by the
WPADS manuscript. It closes the gap between a source-only software archive and
the scientific claims made from the validated HPC campaigns.

- `results/profile-matrix-validity.csv` records run counts, telemetry accuracy,
  variability, and acceptance for every solver/profile matrix.
- `results/controlled-one-core-comparison.csv` records the 15 matched one-core
  SCIP/Gurobi comparisons summarized by profile.
- `results/provenance.json` identifies the dataset subset, source commits,
  Slurm jobs, solver versions, allocation policy, and comparison gate.

The files are processed research results derived from checksummed summaries.
They are not substitutes for raw per-run Analyzer JSON. Raw telemetry can
contain cluster-local paths and is too large for Git; proprietary solver
licenses, large warm-start files, and third-party benchmark archives must not
be redistributed. The repository's evidence exporter creates a sanitized,
checksummed package for a separate data deposit.

The current Zenodo v0.1.0 record predates this directory. Publish these files in
the next software release and link that version to the final evidence dataset.
Do not claim that v0.1.0 already contains publication data.

