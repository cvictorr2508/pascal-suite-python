from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_bibliography_provenance.py"


def write_fixture(tmp_path: Path) -> None:
    (tmp_path / "bibliography").mkdir()
    manifest = {
        "schema_version": 1,
        "collection": {
            "name": "Test collection",
            "zotero_collection_key": "ABCDEFGH",
            "audited_on": "2026-09-10",
            "top_level_item_count": 2,
        },
        "records": [
            {
                "cite_key": "alpha2024",
                "zotero_item_key": "AAAA1111",
                "title": "Alpha",
                "year": 2024,
                "locator": {"type": "doi", "value": "10.1000/alpha"},
                "review_status": "cited",
                "intended_sections": ["background-and-related-work"],
            },
            {
                "cite_key": "beta2025",
                "zotero_item_key": "BBBB2222",
                "title": "Beta",
                "year": 2025,
                "locator": {"type": "url", "value": "https://example.org/beta"},
                "review_status": "approved",
                "intended_sections": ["results-discussion"],
            },
        ],
    }
    (tmp_path / "bibliography" / "zotero-manuscript.json").write_text(
        json.dumps(manifest), encoding="utf-8", newline="\n"
    )
    (tmp_path / "references.bib").write_text(
        """@article{alpha2024,
  title = {Alpha},
  doi = {10.1000/alpha}
}

@misc{beta2025,
  title = {Beta},
  url = {https://example.org/beta}
}
""",
        encoding="utf-8",
        newline="\n",
    )
    (tmp_path / "index.qmd").write_text(
        "A reviewed statement [@alpha2024].\n", encoding="utf-8", newline="\n"
    )


def run_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_accepts_cited_and_approved_records(tmp_path: Path) -> None:
    write_fixture(tmp_path)

    result = run_checker(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "records=2 cited=1 approved=1" in result.stdout


def test_rejects_unknown_manuscript_citation(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    (tmp_path / "index.qmd").write_text(
        "Unsupported [@unknown2026].\n", encoding="utf-8", newline="\n"
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "manuscript citation is missing from references.bib" in result.stdout


def test_rejects_private_export_fields(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    bib_path = tmp_path / "references.bib"
    with bib_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write("\n% file = {C:\\Users\\researcher\\paper.pdf}\n")

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "local path or local-only URI" in result.stdout


def test_rejects_cited_record_not_used_by_manuscript(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    (tmp_path / "index.qmd").write_text("No citation.\n", encoding="utf-8")

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "manifest record marked cited is unused" in result.stdout


def test_rejects_locator_drift(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    bib = (tmp_path / "references.bib").read_text(encoding="utf-8")
    (tmp_path / "references.bib").write_text(
        bib.replace("10.1000/alpha", "10.1000/wrong"),
        encoding="utf-8",
        newline="\n",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "locator does not match manifest" in result.stdout

