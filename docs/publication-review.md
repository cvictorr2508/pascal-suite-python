# Pre-submission evidence review

This procedure audits existing fixed-budget campaigns; it does not submit Slurm
jobs or run Gurobi/SCIP. Use the already activated Python environment. Keep the
original campaign directories unchanged.

The scientific contract is explicit minimization with a 300-second solver time
limit. Gurobi `OPTIMAL`/`TIME_LIMIT` and SCIP `optimal`/`timelimit` are expected
terminal states. Objective, bound, gap, status, and node-count fields are
provenance only: they never select telemetry attempts and cross-solver objective
equality is not an acceptance rule.

## Run on NPAD

After the manual privacy/file, dataset-authorship, and historical-hardware
reviews are complete, create a fresh publication package:

```bash
python -m pytest -q
python scripts/check_bibliography_provenance.py
python scripts/prepare_publication_review.py \
    --gurobi-root resultados_finais/gurobi_hard_profiles_minimize_300s \
    --scip-root resultados_finais/scip_hard_profiles_minimize_300s \
    --output-dir resultados_finais/publication_review_v2_0_0 \
    --privacy-reviewed \
    --authorship-reviewed \
    --hardware-reviewed
```

The output directory and its `.tar.gz` must not already exist. Select a new,
explicit suffix for a repeated audit; never remove or overwrite prior evidence.
Exit 0 means the scientific quality gate passes, 3 means evidence was produced
but that gate failed, and 2 means structural/export failure. `publication_ready`
becomes true only when the scientific gate and all three explicit manual-review
flags pass. The dataset license is MIT.

The scientific gate requires the controlled comparison gate, at least five
energy-valid one-core runs per solver/workload/profile, unique metadata joining
by configuration and start-time containment, the accepted fixed-budget terminal
states, finite incumbent objectives, explicit effective minimization, and the
shared 300-second budget recorded in the matrix summaries. Missing gaps remain
unknown. The historical Gurobi `applied` flag establishes start-file loading,
not incumbent acceptance.

Return `publication_audit.json`, `environment_inventory.json`,
`run_quality.csv`, and the archive checksum for review. Do not paste entire raw
telemetry into chat. The archive retains every attempt, including rejected
measurements. The environment inventory reports observed sample spacing rather
than only the nominal rate and leaves unavailable historical hardware details
unresolved. Do not run `lscpu` on a login node and present it as campaign
hardware.

## Archive contents and boundaries

- `campaigns/`: sanitized Analyzer JSON, base configurations, per-run metadata,
  research manifests, full summaries, and invalid attempts.
- `publication_audit.json`: pair-level coverage decisions, manual-review flags,
  policy, and row-level reasons.
- `run_quality.csv`: terminal state, objective, bound, gap when recorded, sample
  period, and absolute energy/time for regions 0, 0.1, and 0.2.
- `environment_inventory.json`: recorded provenance, allocation, and sampling.
- `comparison/`: reconstructed controlled fixed-budget comparison.
- `artifact_inventory.json`: original and distributed SHA-256 identities.
- `LICENSE`, `scripts/`, `scripts/LICENSE`, `README.md`, and `SHA256SUMS`:
  MIT licensing, reconstruction code, data dictionary, privacy transformations,
  and integrity checks.

No benchmark instances, start files, solver binaries, solver licenses, or
arbitrary logs are included. This is a sanitized derivative, not a byte-identical
raw archive. Paths, hostnames, commands, and free-form errors are redacted.
Invalid finite measurements are preserved; NaN/Infinity become tagged strings.
Manual inspection remains mandatory: this utility is not a complete secret
scanner. All analysis runs locally on the available JSONs and needs no solver
license.

## Minimal Zenodo sequence

1. Merge the reviewed repository change and publish software release `v0.2.0`.
   Keep the stable software concept DOI `10.5281/zenodo.22695373`; record the new
   version DOI only after Zenodo creates it.
2. Run the command above against the corrected Gurobi and composed SCIP
   fixed-budget matrices. Require `quality_audit_accepted=True` and
   `publication_ready=True`.
3. Inspect the archive and verify `SHA256SUMS`. Upload the new archive, its
   top-level checksum file, and its human-readable `README_DATASET.md` to draft
   `https://zenodo.org/uploads/23071850`. Retain the reviewed figure,
   `dual_solver_comparison.json`, `solver_measurements.csv`, and
   `paired_one_core_comparisons.csv`.
4. Publish the dataset only after its metadata names the software dependency and
   the exact generating commits. Link dataset to software with `Requires`; link
   the new software version to the dataset with `IsRequiredBy` when available.
5. Update the manuscript and GitHub Pages with the published dataset DOI. Do not
   label a submitted manuscript as an accepted conference article.

The 5% RAPL criterion measures internal acquisition/integration consistency,
not external-meter accuracy. CV in the published matrix is for region 0 energy;
solver ratios concern region 0.2. Model/start preparation between the child
regions belongs to region 0 and must not be attributed to solve execution.
