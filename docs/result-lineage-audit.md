# Result-lineage audit, 2026-10-10

## Scope and editorial freeze

This is repository maintenance, not a new experiment or manuscript revision.
WPADS 2026 submission 36682 remains under peer review according to the author.
The submitted PDF and submission-system HTML are preserved outside Git. Their
SHA-256 values are recorded in `publication/result-generations.json`.
No solver was run, published deposit modified, or manuscript file edited for
this reconciliation. A fresh editorial decision has not been independently
retrieved from JEMS.

## Experimental generations

| Generation | Source and contract | Interpretation |
| --- | --- | --- |
| Historical September 11 | Gurobi `915bd79`, job 2084725; SCIP `b03b6f2`, job 2084503; source-declared maximization, without the later minimization override | Retain the original three files at `publication/results/`; not corrected CFL minimization evidence |
| Corrected September 28/30 | Both solvers `fbbf7d7`; explicit minimization; native 300-second budget; five instances and three profiles | Submission-associated results in `publication/results/corrected-minimize-300s-v2/` |
| Software release 0.2.0 | Release commit `7e97358`; version DOI `10.5281/zenodo.23082727` | An archived software snapshot, not the campaign execution commit |

The historical CSVs were introduced before the objective-direction correction.
They were not replaced when the reviewed documentation and Quarto tables were
updated. Thus their numerical disagreement is a documented generation mismatch,
not evidence that the submitted PDF uses the historical values. Comparing the
submitted PDF with the corrected report confirmed the corrected table values
and fixed-budget ratios. Preserve the PDF as submitted.

The corrected comparison is dataset version
[2.0.0](https://doi.org/10.5281/zenodo.23071850), not historical dataset
[1.0.0](https://doi.org/10.5281/zenodo.22709483). Its two CSV files are copied
byte-for-byte. The comparison JSON remains external because it includes
nonessential cluster-local runtime identifiers. A compact path-neutral extract
records its hash, contract, gates, dataset fingerprints, and input hashes here.

## Retry accounting and verification boundary

The original full gate, job 2133014, failed because SCIP/default/instance 15
retained four valid observations of six. Retry job 2135641 produced two valid
observations in a separate root. The recorded composition replaced original
positions `1;2;2` and `1;2;3` with retry positions `1;0;1` and `1;0;2` in
chronological order, based only on telemetry validity.

The accepted logical matrix has 360 positions, 336 valid observations, and 24
invalid observations. The composition record reports 362 physical attempts.
The public archive distributes 360 logical metadata records. It does not
distribute the original two replaced attempts or the standalone
`composition_manifest.json` referenced by the composed SCIP research manifest.
The policy is documented, but the complete physical replacement chain cannot
be independently reconstructed from that archive alone. Do not report the
offline consistency check as certification of all 362 physical attempts.

SCIP/presolve-off maximum region-0 CV is 10.538866%, above the preferred 10%
target. This is disclosed and non-binding; all mandatory gates remain accepted.
Native time limits can overrun wall time. These results do not establish time
to optimality or equivalent terminal solution quality.

## Read-only Zenodo findings

The October 10 read-only inspection found:

1. The outer SHA256SUMS verifies five of its six listed files. The published
   PNG hash is `2f4f7d6699765bee9d3f2d972628f581b1fc28df135bdfb7995275c71ff5ba1a`,
   while the listed expected hash is
   `9fbf248cdb232f60432a8663b23e0b0cf4d1d255f51c964637972d358b2a1244`.
   The expected value identifies the repository PNG. The distributed PNG is a
   different encoding/crop; its decoded RGB pixels match the image embedded in
   the submitted PDF. The discrepancy is archival integrity metadata, not
   evidence of a wrong scientific plot.
2. The archive hash is
   `82ce879957232058d5022b7de331946de2dd25e624b00c821191dd6fbea64696`.
   All 397 entries covered by its internal manifest verified. The archive has
   398 files including the checksum manifest itself.
3. The standalone composition manifest and replaced originals are absent as
   described above. Retrieve and check the preserved NPAD copies read-only
   before deciding on any archival correction.
4. The archive is path-neutral, but the outer comparison JSON still includes
   cluster-local host and Python executable identifiers. Sanitization therefore
   differs between the archive and the separately uploaded report.

No Zenodo metadata, files, versions, or licenses were changed. Possible
corrections require a separate author decision after investigation.

## Automated checks and remaining decisions

Run `python scripts/check_publication_provenance.py`. Optionally add
`--submission-pdf <preserved-PDF>` and `--submission-html <preserved-HTML>` to
verify the local submission copies without copying or editing them.

The check pins both generations' file hashes, checks 60 configuration records
and 15 pairs, recomputes ratios and profile medians, checks 360 logical attempt
counts, and verifies the existing Quarto and research-MVP tables at their
reported precision. It deliberately returns `archival_chain_complete=false`.
It does not reread raw RAPL samples or infer solver quality from an accepted
telemetry gate.

Pending author decisions are the manual merges into `develop`, whether the
operational-memory documents should ever be promoted to `main`, and whether a
future archive correction should address the PNG checksum, missing retry chain,
and outer-report sanitization. The live manuscript's software-version wording
also needs an editorial decision; it is not changed in this maintenance PR.
Scientific manuscript revisions and additional HPC runs remain deferred until
the peer-review decision and explicit authorization.
