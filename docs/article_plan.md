# Article and peer-review plan

## Current publication state

Title: `Reproducible Regional Energy Telemetry for Mathematical Optimization
Solvers on HPC Systems`.

Venue: WPADS 2026. Submission identifier: 36682. Status as of 2026-10-09:
submitted and awaiting peer review.

The submitted PDF and submission-system export are immutable records. The
Quarto manuscript is the maintained repository source, but changes made after
submission do not retroactively alter the submitted article.

## Stable scientific content

The submitted study is bounded by:

- explicit minimization after native model import;
- a shared 300-second fixed solver budget;
- five MILPBench hard CFL instances;
- `default`, `presolve-off`, and `warm-start` profiles;
- six attempts per configuration and at least five valid telemetry attempts;
- Gurobi core/thread treatments 1, 2, and 4;
- a matched one-core Gurobi-SCIP comparison;
- regional RAPL telemetry with mandatory consistency and replication gates;
- one disclosed preferred-CV exceedance;
- descriptive fixed-budget claims rather than universal solver rankings.

Do not expand this scope during a peer-review correction unless the reviewers
explicitly require new evidence and the authors approve a separate experiment.

## Public supporting material

- Quarto manuscript: <https://cvictorr2508.github.io/pascal-suite-python/>.
- Software concept DOI: <https://doi.org/10.5281/zenodo.22695373>.
- Software version 0.2.0: <https://doi.org/10.5281/zenodo.23082727>.
- Dataset concept DOI: <https://doi.org/10.5281/zenodo.22709482>.
- Dataset version 2.0.0: <https://doi.org/10.5281/zenodo.23071850>.
- Public PaScal Viewer: <https://pascalsuite.imd.ufrn.br/viewer/>.
- Viewer implementation record:
  <https://gitlab.com/lappsufrn/pascalsuite-viewer/-/merge_requests/15>.

## Peer-review response workflow

When reviews arrive:

1. Archive the review text and decision notice outside the public repository if
   confidentiality applies.
2. Create a response matrix with one row per reviewer comment: requested change,
   interpretation, evidence needed, proposed response, affected files, author
   decision, and completion status.
3. Classify each item as editorial, clarification, reanalysis, code change,
   evidence correction, or new experiment.
4. Create a new branch from the then-current integration base. Do not reuse the
   submission branch.
5. Update Quarto first. Apply only author-approved surgical edits to the LaTeX
   source used for the venue.
6. For numerical changes, trace every value to a checksummed machine-readable
   artifact. Do not transcribe values from plots.
7. Run bibliography provenance, tests, linting, Quarto render, page-limit, and
   visual PDF checks as applicable.
8. Preserve a distinct revised PDF and response letter. Never overwrite the
   original submission files.
9. Review repository, GitHub Pages, software release, and Zenodo consequences
   separately. A manuscript correction does not automatically require a new
   software or dataset version.

## Decision rules for new archival versions

- Create a new software release only for a material code, contract, or
  reproducibility change.
- Create a new dataset version only if evidence, processed results, manifests,
  or archived documentation materially change.
- A wording-only manuscript correction normally requires neither.
- Keep concept DOIs stable and cite a version DOI when exact archived content
  matters.

## Final revision checklist

- Authors and `Samuel Xavier-de-Souza` spelling are consistent.
- Claims remain bounded to the recorded environment and fixed-budget design.
- Objective sense, time budget, attempt counts, invalid telemetry, retry policy,
  and preferred-CV exceedance are disclosed consistently.
- Tables, narrative, abstract, conclusion, and machine-readable results agree.
- Viewer figures identify solver, profile, instances, core treatments, regions,
  and normalization semantics.
- Every DOI and URL resolves and supports the cited statement.
- The body respects the venue page limit; references are treated according to
  the current call.
- The generative-AI declaration remains present if required by the applicable
  policy.
- Submitted and revised artifacts have distinct filenames and checksums.

Until a review decision arrives, the correct action is preservation and status
monitoring, not further expansion of the submitted study.
