# SCIP retry parameter audit, 2026-10-11

## Verified finding

The preserved SCIP/default/instance-15 originals use seed 10002. Both retries
from job 2135641 use seed 10000. The runner at campaign commit `fbbf7d7` derives
the seed as `10000 + input_idx`. Filtering the workload list to a single input
changed the index from 2 to 0 and consequently changed the executed seed.

The compositor remaps the copied metadata index to 2 but retains seed 10000.
Do not change the recorded seed to 10002: that would misrepresent execution.
SHA-256 verification of the four author-supplied files passed. Their hashes
and the author decision are recorded in
`publication/audits/scip-retry-seed-20261011.json`, a new audit record rather
than an alteration of the frozen result generations.

Static review shows whole Analyzer-record copying into a new output root.
It does not establish byte-level identity of every NPAD input or independently
revalidate raw power. The compositor does not check seed equivalence. Some
manifest fields, including source commit and validity counts, are literals in
the script rather than conclusions it verifies.

## Scope of impact

Two observations in SCIP/default/instance 15 differ from the original seed.
Their telemetry validity is separate from parameter equivalence. Four valid
original observations remain under seed 10002, below the five-observation
same-contract replication requirement. The logical matrix's recorded 336 valid
telemetry observations must not be described as certification of seed-matched
replication in every cell.

The directly affected pair is the one-core default-profile comparison for
instance 15. Its duration, energy and EDP medians and default-profile aggregates
may depend on the retries. The affected profile's variability and replication
interpretation also require qualification. The compositor does not replace
Gurobi records or SCIP presolve-off/warm-start records. This bounds the direct
replacement scope; it does not prove that the article has no affected claim.

The corresponding author, speaking for the coauthors on October 11, decided to
preserve submission 36682 unchanged because its contribution focuses on Gurobi.
Record that as an editorial decision, not a demonstrated zero numerical effect
and not a waiver of the seed-equivalence finding. No manuscript, Quarto, Pages,
published dataset, historical result or solver runner is changed by this audit.

## Read-only NPAD check

Run from a checkout containing the reviewed audit script, with Python 3.13.
Do not rerun the old compositor or the matrix summarizer: they write files.
The command below opens evidence only for reading and prints JSON to stdout.
It does not require cloud access, solvers, or a new Slurm allocation.

```bash
run_root="/home/vrrcelestino/pascal-suite-python-evidence/pr22-corrected-profile-matrices/run-20260928T201840Z"

PYTHONDONTWRITEBYTECODE=1 python scripts/audit_scip_retry_composition.py \
    --manifest "$run_root/composed/scip_hard_profiles_minimize_300s/composition_manifest.json"
audit_rc=$?
printf 'retry_chain_audit_rc=%s\n' "$audit_rc"
```

Exit 3 is the expected known parameter mismatch if evidence checks otherwise
pass. Exit 2 identifies an evidence-check error, missing file or schema issue.
Exit 0 requires matching checked parameters; it is not expected for this chain.
There is no shell-level `exit`, no output file and no evidence regeneration.

The script checks the six source hashes, declared derived hashes, removed and
added metadata, unchanged retained default metadata, full Analyzer-document
replacement equality, untouched profiles, source commits and effective metadata
parameters. It reports original/retry/composite region-0 and region-0.2 medians
from existing valid-run summaries, not from a new power integration. Original four-run statistics are
under-replicated diagnostics, not a newly accepted comparison. Their changes
cannot isolate a causal seed effect from run timing, hardware or other factors.
Full NPAD execution remains pending until the author returns its output.
The composite summary's observed hash is printed for comparison with the
preserved checksum list. Stored summary measurements are not independently
recomputed and scheduler allocation equivalence is outside this narrow check.

## Post-congress backlog and boundaries

Privacy sanitization removes unnecessary identifiers. Experimental validation
checks whether observations share the intended contract. Neither operation can
repair a seed mismatch in an already executed observation.

After the congress, plan a separate reviewed change that preserves stable
workload identity and explicit effective seeds when preparing a filtered retry.
Add fail-closed checks for seed and other parameter differences before admitting
retries, then review archival completeness and privacy. Keep original and
corrected generations distinct. Any future experiments or Zenodo revision need
new explicit authorization. No new jobs, retroactive seed edits, automatic
merges, public deployment or article edits are authorized now.
