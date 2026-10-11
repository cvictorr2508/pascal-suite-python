# Publication data and results

This directory preserves distinct experimental generations. Do not use the
historical CSVs at `results/` as the corrected WPADS submission results.

- `results/profile-matrix-validity.csv`,
  `results/controlled-one-core-comparison.csv`, and `results/provenance.json`
  remain byte-for-byte historical records of the September 11 generation.
  The comparison CSV has three profile summaries, not 15 individual pairs.
- [Corrected generation](results/corrected-minimize-300s-v2/) identifies the
  explicit-minimization, 300-second results associated with submission 36682.
  It includes six validity rows, three profile summaries, 15 individual pairs,
  60 configuration measurements, and a path-neutral provenance extract.
- [Generation registry](result-generations.json) pins both generations by
  identifiers and SHA-256 values. The corrected CSV copies match dataset
  version [2.0.0](https://doi.org/10.5281/zenodo.23071850).

The files are processed research results derived from checksummed summaries.
They are not substitutes for raw per-run Analyzer JSON. Raw telemetry can
contain cluster-local paths and is too large for Git; proprietary solver
licenses, large warm-start files, and third-party benchmark archives must not
be redistributed. The repository's evidence exporter creates a sanitized,
checksummed package for a separate data deposit.

The software version 0.2.0 archive still contains the historical CSVs. Its
release commit is distinct from the corrected campaigns' source commit. This
maintenance change reconciles the repository without modifying either archive.

Run the offline check with `python scripts/check_publication_provenance.py`.
It checks file integrity, configuration coverage, replication counts, paired
ratios, rounded summaries, and the existing Quarto/documentation tables. It
does not execute solvers, regenerate telemetry, or certify the full physical
retry chain. See [the October 10 audit](../docs/result-lineage-audit.md) for
verified limitations and decisions still requiring authorization.

