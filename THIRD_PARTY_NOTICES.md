# Third-party notices

This repository vendors a historical LaTeX style resource derived from
material distributed for events of the Sociedade Brasileira de Computação
(SBC).

## License boundary

This notice does not declare a repository-wide license and does not relicense
either original project code or third-party material. Rights in third-party
files remain with their respective authors or upstream distributors.

## SBC LaTeX style resource

Path:

- `_extensions/sbc/sbc-template.sty`

Provenance:

- imported through `cvictorr2508/quarto-sbc` at commit
  `88eaa11eeee9f86cd8594466e4644b321c8d7b75`;
- derived from the classic SBC LaTeX style supplied to that template project;
- the original header credits Jomi Hubner and Rafael Bordini (June 2001), with
  updates noted for March 2005 and December 2017;
- the repository copy preserves active LaTeX behavior while normalizing
  malformed comment characters to UTF-8 and translating repository-facing
  comments to English;
- original reference-file hashes and the adaptation boundary are recorded in
  `docs/SBC_TEMPLATE_PROVENANCE.md`.

The style file is third-party material. Users and redistributors are
responsible for complying with applicable upstream terms and venue-specific
requirements.

## Historical SBC bibliography style

The project-supplied `sbc.bst` is not vendored. Its reference SHA-256 and
compatibility analysis are recorded in
`docs/SBC_TEMPLATE_PROVENANCE.md`. The executable adapter uses the standard
`apalike` formatter with natbib punctuation configured to reproduce the
documented SBC author-year citation behavior.

## Attribution and venue requirements

This integration is independent and is not an official source of SBC
publication rules. Authors must verify the current instructions and licensing
requirements of the intended conference, journal, workshop, or event.
