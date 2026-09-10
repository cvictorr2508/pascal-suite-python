#!/usr/bin/env python3
"""Run structural regression checks on the rendered SBC manuscript PDF."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "_manuscript"
ARTIFACT_DIR = ROOT / "artifacts"
EXPECTED_MARKERS = (
    "Reproducible Regional Energy Telemetry for Mathematical Optimization "
    "Solvers on HPC Systems",
    "Victor Rafael R. Celestino",
    "Kayo Gonçalves e Silva",
    "Samuel Xavier Souza",
    "University of Brasília (UnB)",
    "LAPPS",
    "UFRN",
    "Abstract.",
    "Resumo.",
    "Introduction",
    "Experimental Method",
    "Results",
    "Threats to Validity",
    "References",
)


def require_program(name: str) -> str:
    """Return an executable path or fail with an actionable message."""
    path = shutil.which(name)
    if path is None:
        raise SystemExit(f"required program not found: {name}")
    return path


def find_single(pattern: str) -> Path:
    """Return one generated artifact and reject missing or ambiguous output."""
    matches = sorted(OUTPUT_DIR.rglob(pattern))
    if len(matches) != 1:
        raise SystemExit(
            f"expected exactly one {pattern!r} under {OUTPUT_DIR}, "
            f"found {len(matches)}"
        )
    if matches[0].stat().st_size == 0:
        raise SystemExit(f"generated artifact is empty: {matches[0]}")
    return matches[0]


def normalized_text(value: str) -> str:
    """Normalize renderer whitespace while retaining textual content."""
    return re.sub(r"\s+", " ", value.replace("-\n", "")).strip()


def command_output(arguments: list[str]) -> str:
    """Run a required command and return UTF-8 output."""
    result = subprocess.run(
        arguments,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def main() -> int:
    """Validate the rendered manuscript and write review artifacts."""
    pdf = find_single("*.pdf")
    tex = find_single("*.tex")

    tex_text = tex.read_text(encoding="utf-8")
    if "\\usepackage{sbc-template}" not in tex_text:
        raise SystemExit("generated TeX does not load sbc-template")
    if "\\tableofcontents" in tex_text:
        raise SystemExit("SBC manuscript must not contain a table of contents")

    pdftotext = require_program("pdftotext")
    pdfinfo = require_program("pdfinfo")
    pdftoppm = require_program("pdftoppm")

    text = normalized_text(command_output([pdftotext, str(pdf), "-"]))
    missing = [marker for marker in EXPECTED_MARKERS if marker not in text]
    if missing:
        header_context = text[:2000]
        raise SystemExit(
            f"PDF text is missing expected markers: {missing}\\n"
            f"PDF text context: {header_context}"
        )

    info = command_output([pdfinfo, str(pdf)])
    page_match = re.search(r"^Pages:\s+(\d+)\s*$", info, re.MULTILINE)
    if page_match is None or int(page_match.group(1)) < 1:
        raise SystemExit("could not confirm a positive PDF page count")
    page_count = int(page_match.group(1))

    ARTIFACT_DIR.mkdir(exist_ok=True)
    first_page_stem = ARTIFACT_DIR / "sbc-first-page"
    subprocess.run(
        [
            pdftoppm,
            "-f",
            "1",
            "-singlefile",
            "-png",
            "-r",
            "144",
            str(pdf),
            str(first_page_stem),
        ],
        check=True,
    )
    first_page = first_page_stem.with_suffix(".png")
    if not first_page.is_file() or first_page.stat().st_size == 0:
        raise SystemExit("Poppler did not produce a nonempty first-page image")

    report = {
        "schema_version": 1,
        "pdf": pdf.relative_to(ROOT).as_posix(),
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "pages": page_count,
        "markers": list(EXPECTED_MARKERS),
        "first_page": first_page.relative_to(ROOT).as_posix(),
    }
    report_path = ARTIFACT_DIR / "pdf-regression.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"pdf_regression=accepted pages={page_count}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
