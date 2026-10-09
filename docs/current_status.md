# Current research status

Last reviewed: 2026-10-09.

## Executive status

The corrected software, evidence dataset, documentation, Viewer integration,
and manuscript are complete for the submitted WPADS 2026 study. The article
`Reproducible Regional Energy Telemetry for Mathematical Optimization Solvers
on HPC Systems` was submitted as submission 36682 and is awaiting peer review.

No experiment, repository, GitHub Pages, Zenodo, or manuscript-publication
action is currently required. Resume scientific work only in response to a
reviewer/editorial request or a newly verified material issue.

## Verified milestones

| Object | Status |
| --- | --- |
| Corrected solver contract | Explicit minimization and matched 300-second budget validated |
| Controlled matrices | Gurobi and SCIP profile matrices accepted under the declared gates |
| Controlled comparison | Accepted for the bounded one-core fixed-budget comparison |
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
