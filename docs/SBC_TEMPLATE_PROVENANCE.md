# SBC template provenance

The PDF format used by this manuscript is derived from the classic LaTeX
template distributed for events of the Sociedade Brasileira de Computação
(SBC). The Quarto integration was imported from
[cvictorr2508/quarto-sbc](https://github.com/cvictorr2508/quarto-sbc) at commit
`88eaa11eeee9f86cd8594466e4644b321c8d7b75`.

## Reference package recorded by quarto-sbc

The upstream integration was checked against the archive supplied to that
project:

- archive: `sbc-template-latex.zip`
- SHA-256:
  `4f9afbf2428d8403de56c3ecbae2bb4e17ec5efe35debbc07184f24ee0d8430b`

| Reference file | SHA-256 | Integration status |
|---|---|---|
| `sbc-template.sty` | `dbe513d56dde32bedc53dcf7b9efba052ff1b3b747037ed2f284f7095a91e895` | Normative layout resource. Comment encoding/language was normalized without changing active LaTeX behavior. |
| `sbc.bst` | `d884c6793e4ea54d13f5c751b3d6f4ea529a62d0906cd9774f2ec350b394691f` | Inspected and hash-recorded, but not vendored. |
| `sbc-template.tex` | `7b1c4682b13c523968cea1ea367eda4477952e49628b1527312e040a6f3b776b` | Behavioral reference for title, authors, affiliations, Abstract, Resumo, and layout. |

These hashes identify the original project-supplied files, not the adapted
copies in this repository.

## Adaptation boundary

1. `sbc-template.sty` remains the normative source for page geometry,
   typography, title block, sections, captions, Abstract, and Resumo.
2. `_extensions/sbc/template.tex` maps Quarto/Pandoc metadata and document
   output into the historical style and contains current natbib/hyperref
   compatibility handling.
3. HTML is a companion scholarly representation; it is not claimed to
   reproduce the SBC PDF layout pixel for pixel.
4. UTF-8 is used consistently. The conflicting UTF-8 and Latin-1 declarations
   in the historical example document are not reproduced.
5. Repository-facing comments and engineering documentation are English.
   Required interface terms such as `Resumo`, proper nouns, citation titles,
   and upstream identifiers are preserved.

Future modifications to imported SBC resources must be documented here and
must not be described as official SBC changes without an authoritative source.
