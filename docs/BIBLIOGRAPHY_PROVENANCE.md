# Bibliography provenance and review policy

The Quarto manuscript uses a reviewed bibliography derived from the Zotero
collection **PaScal Suite Python — Manuscript**. Zotero is the research queue;
the repository remains the reproducible publication record. Collection
membership alone does not authorize a citation.

`bibliography/zotero-manuscript.json` maps every reviewed Zotero item key to a
stable manuscript citation key, a persistent DOI or URL, its review status,
and the manuscript sections for which it may provide evidence. Zotero item
keys identify records inside one Zotero library. They are intentionally kept
distinct from stable BibTeX keys used by Quarto.

## Iterative review states

- `candidate`: retained in the collection for assessment, but absent from the
  canonical bibliography and manuscript;
- `approved`: scientifically reviewed and retained in `references.bib`, but
  not necessarily cited yet;
- `cited`: approved, present in `references.bib`, and cited in `index.qmd`;
- `excluded`: reviewed and intentionally omitted from both the canonical
  bibliography and manuscript.

For each new literature batch:

1. add candidate records to the dedicated Zotero collection;
2. deduplicate by DOI, then by normalized title when no DOI exists;
3. verify creators, year, venue, DOI or canonical URL, and document type;
4. classify the intended evidentiary role as background, related work,
   method, results discussion, or excluded;
5. obtain scientific approval before changing a record to `approved` or
   `cited`;
6. update the provenance manifest and a sanitized `references.bib` entry;
7. add manuscript citations only for records marked `cited`;
8. run the bibliography checker and render the complete Quarto manuscript.

## Privacy and reproducibility boundary

Do not commit a raw export of the Zotero library or collection. Raw exports may
contain local attachment paths, abstracts, personal tags, annotations, or
other fields that are unnecessary for publication. The canonical
`references.bib` contains only reviewed bibliographic fields and stable
locators. The repository checker rejects common private export fields,
local filesystem paths, local-only URIs, unknown citation keys, locator drift,
and inconsistent review states.

Run the offline, deterministic validation with:

```bash
python scripts/check_bibliography_provenance.py
```

This command does not contact Zotero and is therefore suitable for CI. Zotero
is consulted during curated literature review; CI validates only the committed
and reviewable publication inputs.

Zenodo updates are intentionally deferred until the manuscript and its GitHub
Pages rendering have reached a final reviewed state.

