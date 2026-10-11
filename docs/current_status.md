# Current research status

Last reviewed: 2026-10-11.

## Executive status

The corrected campaigns, Viewer integration, and manuscript support the
submitted WPADS 2026 study. Repository and archival traceability still have
documented maintenance issues. The article
`Reproducible Regional Energy Telemetry for Mathematical Optimization Solvers
on HPC Systems` was submitted as submission 36682 and is awaiting peer review.

The author authorized a limited maintenance sprint on October 10: propose
`main` to `develop` history synchronization, reconcile result generations in
an independent PR, and update this operational memory. No automatic merges,
Pages publication, Zenodo changes, manuscript edits, or new HPC runs are
authorized. Scientific revisions remain deferred until peer review or a
separately approved material correction.

## Verified milestones

| Object | Status |
| --- | --- |
| Corrected solver contract | Explicit minimization and matched 300-second budget validated |
| Controlled matrices | Historical gates passed; SCIP/default retry seed equivalence failed in the October 11 audit |
| Controlled comparison | Recorded gate passed; affected SCIP/default pair requires parameter-equivalence qualification |
| Software | Version 0.2.0 published; DOI `10.5281/zenodo.23082727` |
| Dataset | Corrected version 2.0.0 published; DOI `10.5281/zenodo.23071850` |
| Viewer integration | GitLab MR !15 merged and publicly deployed |
| Public manuscript | GitHub Pages deployment successful |
| Conference article | WPADS 2026 submission 36682; peer review pending |

The stable concept DOIs are `10.5281/zenodo.22695373` for software and
`10.5281/zenodo.22709482` for the dataset.

## Repository state relevant to this document

At creation of this status file, public `main` points to merge commit
`810317984e1b4050db05634ce7d30de64145fdba` and includes the Viewer public-access
documentation. The research-memory change is intentionally proposed against
`develop`. Branch positions are transient; verify them before any future merge
or release.

## Preserved submission records

The user's final submitted PDF and the submission-system HTML export are
immutable records. Do not overwrite them when preparing a revision. A revised
manuscript must receive a distinct filename and be linked to the corresponding
review round.

## October 10 diagnosis and provenance maintenance

Verified facts:

- The historical CSVs at `publication/results/` describe the September 11
  generation, with Gurobi source `915bd79` and SCIP source `b03b6f2`. They do
  not describe the corrected minimization/300-second campaigns at `fbbf7d7`.
- The corrected values already appear in `docs/research-mvp.md`, `index.qmd`,
  the accepted comparison report, and the submitted PDF. The divergence does
  not establish that the submitted article has incorrect numerical results.
- The corrected matrix has 360 logical attempts and 336 telemetry-valid
  attempts. The recorded retry policy reports 362 physical attempts, including
  two chronological telemetry retries for SCIP/default/instance 15.
- The public v2.0.0 archive has 360 logical metadata records, but does not
  distribute the referenced standalone composition manifest or the two
  original replaced attempts. Full physical-chain verification is pending.
- The outer dataset checksum manifest has a PNG mismatch. Five other listed
  files and all 397 internally checksummed archive entries verified. The
  published PNG's decoded pixels match the submitted PDF figure.
- The outer comparison JSON includes cluster-local runtime identifiers even
  though the archive is path-neutral. Sanitization scope needs review.

Pending work is limited to traceability: preserve historical bytes, identify
the corrected generation separately, add offline consistency regression
checks, and inspect the preserved NPAD retry/manifest records read-only.
Do not infer poor scientific selection or incorrect submitted values from
missing distributed provenance alone. Do not certify the full 362-attempt
chain until the missing records have been checked.

## Integration and approval state

- PRs #29 (history synchronization), #30 (result lineage) and #28 (operational
  memory) were reviewed and merged into `develop`, verified through GitHub.
- The October 11 retry audit is a separate maintenance change based on
  `develop`. It does not replace historical or corrected published results.
- Promotion of the operational memory to `main` remains an explicit author
  decision. Zenodo corrections, new archival versions, and any future Pages
  deployment require separate authorization.

Editorial status is author-reported as awaiting peer review; a fresh JEMS
decision has not been independently retrieved. Preserve submission ID 36682.

## October 11 retry finding and author decision

Preserved NPAD output and four supplied files confirm that the six original
SCIP/default/instance-15 attempts used seed 10002, while two valid retries used
seed 10000. The compositor remapped local input index 0 to 2 without changing
the executed seed. The same-seed original cell retains four valid attempts,
below the requirement of five. Accepted telemetry is not proof of identical
experimental parameters. The old numerical-consistency check does not check
retry parameter equivalence.

The author authorized read-only chain checking, stored-summary diagnostics,
documentation and offline negative tests. Full NPAD source-hash/record
comparison and numerical sensitivity remain pending author-executed output.
See [SCIP retry audit](scip-retry-audit.md) and
`publication/audits/scip-retry-seed-20261011.json`.

Speaking for the coauthors, the author decided to keep submission 36682
unchanged because of its Gurobi focus. This is an editorial decision, not
proof of zero effect on every SCIP-dependent statistic. No manuscript edits,
new jobs, artificial seed correction, Zenodo changes or public deployment are
authorized. Defer stable workload/seed handling, strict retry admission and
SCIP archival/privacy sanitization to post-congress planning under separate
authorization. Preserve every original and retry record.

## Restart triggers

Resume work when one of the following occurs:

- peer-review or editorial comments arrive;
- the conference requests a camera-ready version or metadata correction;
- a material factual, numerical, licensing, privacy, or reproducibility issue
  is verified;
- a new scientific question is explicitly authorized as a separate study.

For reviewer changes, create a new scoped branch, preserve the original
submission, update Quarto first, mirror accepted changes into LaTeX, and rerun
the relevant scientific and publication gates. Create a new Zenodo version only
if evidence or archived artifacts materially change.

## Deliberately deferred work

- No broad refactor or new campaign while peer review is pending.
- No expansion to new solvers, datasets, nodes, or statistical claims within
  the submitted-study maintenance branch.
- No promotion of these operational memory files to `main` without explicit
  review of their value as public documentation.
