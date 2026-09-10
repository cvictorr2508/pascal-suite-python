# SBC PDF regression

The manuscript workflow renders both HTML and the vendored SBC PDF format.
`scripts/check_sbc_pdf.py` performs a deterministic structural regression
after `quarto render`.

The check verifies:

- the PDF and retained TeX source exist and are nonempty;
- the generated TeX loads `sbc-template` and does not add a table of
  contents;
- the PDF contains the draft title, author placeholder, Abstract, Resumo,
  principal scientific sections, and references;
- the PDF has at least one page;
- Poppler can render the first page as a nonempty PNG;
- a path-neutral JSON report records the PDF SHA-256, page count, and checked
  markers.

Run locally after installing Quarto, TinyTeX, and Poppler:

```bash
quarto check
quarto render
python scripts/check_sbc_pdf.py
```

The check is deliberately structural rather than pixel-perfect. Font and PDF
renderer updates can change pixels without changing the scholarly contract.
The first-page PNG is uploaded by CI for human visual review.

Before the pull request becomes ready for review, replace the provisional
author and affiliation metadata and update the corresponding expected markers
in the regression script.
