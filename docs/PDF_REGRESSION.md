# SBC PDF regression

The manuscript workflow renders both HTML and the vendored SBC PDF format.
`scripts/check_sbc_pdf.py` performs a deterministic structural regression
after `quarto render`.

The check verifies:

- the PDF and retained TeX source exist and are nonempty;
- the generated TeX loads `sbc-template` and does not add a table of
  contents;
- the PDF contains the confirmed title, all three authors, both institutional
  affiliations, Abstract, Resumo, principal scientific sections, and references;
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

The expected authorship and affiliation markers are derived from the supplied
SBC manuscript draft and guard against accidental metadata loss during render.
