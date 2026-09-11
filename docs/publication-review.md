# Pre-submission evidence review

This procedure audits existing campaigns; it does not submit Slurm jobs or run
Gurobi/SCIP. Use the already activated Python environment. Keep original campaign
directories unchanged. Do not interpret the original telemetry comparison gate
as a terminal solution-quality check.

## Run on NPAD

```bash
python -m pytest -q
python scripts/check_bibliography_provenance.py
python scripts/prepare_publication_review.py --gurobi-root resultados_finais/gurobi_hard_profiles --scip-root resultados_finais/scip_hard_profiles --output-dir resultados_finais/publication_review_20260911
```

The output directory and its `.tar.gz` must not already exist. Select a new
explicit suffix for a repeated audit; never remove or overwrite prior evidence.
Exit 0 means the post-hoc quality gate passes, 3 means evidence was produced but
the gate failed, and 2 means structural/export failure. `publication_ready` is
always false until manual privacy, hardware-documentation, authorship and file
review are completed. The dataset license is MIT. Do not weaken thresholds to obtain a passing
result without reporting that methodological change.

The quality gate requires the historical telemetry/allocation gate, at least
five energy-valid one-core runs per solver/workload/profile, unique metadata
association by configuration and start-time containment, native optimal status,
finite objectives, and an objective spread of at most
`1e-6 + 1e-6 * max(abs(objective))` across the included runs in each pair.
This is an explicitly post-hoc diagnostic rule, not a claim that the campaigns
used identical stopping tolerances. Missing Gurobi gaps remain unknown. The
historical Gurobi `applied` flag is not evidence of incumbent acceptance.

Return `publication_audit.json`, `environment_inventory.json`, `run_quality.csv`,
and the archive checksum for review. Do not paste the entire raw telemetry into
chat. The archive retains every attempt, including rejected measurements. The
environment inventory reports observed sample spacing, not merely the nominal
rate, and keeps unavailable historical hardware details unresolved. Do not run
`lscpu` on a login node and present it as campaign hardware.

## Archive contents and boundaries

- `campaigns/`: sanitized Analyzer JSON, base configurations, per-run metadata,
  research manifests, full summaries, including invalid attempts.
- `publication_audit.json`: pair-level quality decisions and all row-level reasons.
- `run_quality.csv`: status, objective, gap when recorded, sample period and
  absolute energy/time for regions 0, 0.1 and 0.2.
- `environment_inventory.json`: recorded provenance, allocation and sampling.
- `comparison/`: reconstructed historical time/energy comparisons. Their
  telemetry gate is distinct from `quality_audit_accepted`.
- `artifact_inventory.json`: original and distributed SHA-256 identities.
- `LICENSE`, `scripts/`, `scripts/LICENSE`, `README.md`, `SHA256SUMS`:
  MIT dataset/code licensing, reconstruction, data dictionary, privacy
  transformations and integrity checks.

No benchmark instances, start files, solver binaries, solver licenses, or
arbitrary logs are included. This is a sanitized derivative, not a byte-identical
raw archive. Paths, hostnames, commands and free-form errors are redacted.
Invalid finite measurements are preserved; NaN/Infinity become tagged strings.
Manual inspection is mandatory: this utility is not a complete secret scanner.
All analysis runs locally on the available JSONs and needs no solver license.

## Zenodo sequence before coauthor circulation

1. Review audit outputs and archive contents; resolve scientific gaps and select
   dataset authors explicitly. The dataset license is MIT, matching the software.
2. Complete dataset draft `https://zenodo.org/uploads/22709483` with the reviewed
   archive, a separate checksum file, and a concise human-readable README.
   Reserved DOI `10.5281/zenodo.22709483` is not public until publication.
3. Update the manuscript's availability paragraph with the published dataset
   DOI only after the record is actually published. Link dataset -> manuscript
   using `IsSupplementTo`, and manuscript -> dataset using `IsSupplementedBy`.
   Initially the reviewed manuscript URL may identify the article; replace or
   complement it with its final publication DOI when available.
4. After the repository change is reviewed and merged, archive a new software
   release/version with MIT licensing. Do not replace or delete the immutable
   v0.1.0 files. Use the actual new release DOI, not a guessed future DOI.
   Link dataset -> software using `Requires` when the version is necessary for
   reconstruction, and software -> dataset using `IsRequiredBy`. Cite exact
   generating commit hashes as well as release identifiers.
5. Do not label a coauthor-review manuscript as an accepted conference article.
   A separate manuscript deposit can be a preprint; do not publish it without
   author approval. The existing reviewed GitHub Pages manuscript can provide
   the article link in the meantime.

The 5% RAPL criterion measures internal acquisition/integration consistency,
not external-meter accuracy. CV in the published matrix is for region 0 energy;
the solver ratios concern region 0.2. Model/start preparation between the child
regions belongs to region 0 and must not be attributed to solve execution.
