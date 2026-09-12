#!/usr/bin/env python3
"""Validate the reviewed bibliography, Zotero provenance, and Quarto citations."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ACTIVE_STATUSES = {"approved", "cited"}
KNOWN_STATUSES = ACTIVE_STATUSES | {"candidate", "excluded"}
PRIVATE_FIELD_PATTERN = re.compile(
    r"(?im)^\s*(?:abstract|annote|file|keywords)\s*="
)
LOCAL_PATH_PATTERN = re.compile(
    r"(?i)(?:(?<![a-z0-9])[a-z]:[\\/]|file://|zotero://|/home/|\\\\users\\\\)"
)
ENTRY_PATTERN = re.compile(r"(?m)^@\w+\{\s*([^,\s]+)\s*,")
CITATION_PATTERN = re.compile(r"(?<![\w@])@([A-Za-z0-9][A-Za-z0-9_.:-]*)")


def repeated(values: list[str]) -> list[str]:
    """Return sorted nonempty values that occur more than once."""
    return sorted(key for key, count in Counter(values).items() if key and count > 1)


def normalize_locator(kind: str, value: str) -> str:
    """Normalize identifiers for deterministic comparisons."""
    normalized = value.strip().rstrip("/")
    if kind == "doi":
        normalized = re.sub(r"(?i)^https?://(?:dx\.)?doi\.org/", "", normalized)
        return normalized.lower()
    return normalized


def bib_entries(text: str) -> dict[str, str]:
    """Split BibTeX text into keyed entry blocks without parsing TeX fields."""
    matches = list(ENTRY_PATTERN.finditer(text))
    entries: dict[str, str] = {}
    for index, match in enumerate(matches):
        key = match.group(1)
        if key in entries:
            raise ValueError(f"duplicate BibTeX key: {key}")
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        entries[key] = text[match.start() : stop].strip()
    return entries


def bib_field(entry: str, name: str) -> str | None:
    """Read a simple braced BibTeX field used for DOI/URL verification."""
    match = re.search(
        rf"(?im)^\s*{re.escape(name)}\s*=\s*\{{([^}}]*)\}}\s*,?\s*$",
        entry,
    )
    return match.group(1).strip() if match else None


def load_manifest(path: Path) -> dict[str, Any]:
    """Load the provenance manifest and reject a non-object root."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("bibliography manifest root must be an object")
    return document


def validate_repository(root: Path) -> list[str]:
    """Return all bibliography provenance violations under a repository root."""
    errors: list[str] = []
    manifest_path = root / "bibliography" / "zotero-manuscript.json"
    bib_path = root / "references.bib"
    manuscript_path = root / "index.qmd"

    try:
        manifest = load_manifest(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"cannot load bibliography manifest: {error}"]

    if manifest.get("schema_version") != 1:
        errors.append("bibliography manifest schema_version must equal 1")
    collection = manifest.get("collection")
    if not isinstance(collection, dict):
        errors.append("bibliography manifest collection must be an object")
    else:
        for field in ("name", "zotero_collection_key", "audited_on"):
            if not str(collection.get(field, "")).strip():
                errors.append(f"bibliography manifest collection.{field} is required")

    records = manifest.get("records")
    if not isinstance(records, list) or not records:
        return errors + ["bibliography manifest records must be a nonempty array"]

    cite_keys: list[str] = []
    zotero_keys: list[str] = []
    locator_keys: list[str] = []
    records_by_key: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        label = f"records[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{label} must be an object")
            continue
        cite_key = str(record.get("cite_key", "")).strip()
        zotero_key = str(record.get("zotero_item_key", "")).strip()
        title = str(record.get("title", "")).strip()
        status = str(record.get("review_status", "")).strip()
        sections = record.get("intended_sections")
        locator = record.get("locator")
        if not cite_key:
            errors.append(f"{label}.cite_key is required")
        else:
            cite_keys.append(cite_key)
            records_by_key[cite_key] = record
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", zotero_key):
            errors.append(f"{label}.zotero_item_key is invalid")
        else:
            zotero_keys.append(zotero_key)
        if not title:
            errors.append(f"{label}.title is required")
        if status not in KNOWN_STATUSES:
            errors.append(f"{label}.review_status is unknown: {status!r}")
        if not isinstance(sections, list) or not sections or not all(
            isinstance(section, str) and section.strip() for section in sections
        ):
            errors.append(f"{label}.intended_sections must be a nonempty string array")
        if not isinstance(locator, dict):
            errors.append(f"{label}.locator must be an object")
        else:
            kind = str(locator.get("type", "")).strip()
            value = str(locator.get("value", "")).strip()
            if kind not in {"doi", "url"} or not value:
                errors.append(f"{label}.locator must contain a DOI or URL")
            else:
                locator_keys.append(f"{kind}:{normalize_locator(kind, value)}")

    for value in repeated(cite_keys):
        errors.append(f"duplicate manifest cite_key: {value}")
    for value in repeated(zotero_keys):
        errors.append(f"duplicate manifest zotero_item_key: {value}")
    for value in repeated(locator_keys):
        errors.append(f"duplicate manifest locator: {value}")

    try:
        bib_text = bib_path.read_text(encoding="utf-8")
        manuscript_text = manuscript_path.read_text(encoding="utf-8")
        entries = bib_entries(bib_text)
    except (OSError, UnicodeError, ValueError) as error:
        return errors + [f"cannot read canonical bibliography inputs: {error}"]

    if PRIVATE_FIELD_PATTERN.search(bib_text):
        errors.append("references.bib contains a private or nonessential export field")
    if LOCAL_PATH_PATTERN.search(bib_text):
        errors.append("references.bib contains a local path or local-only URI")

    active_keys = {
        key
        for key, record in records_by_key.items()
        if record.get("review_status") in ACTIVE_STATUSES
    }
    bib_keys = set(entries)
    for key in sorted(active_keys - bib_keys):
        errors.append(f"active manifest record is missing from references.bib: {key}")
    for key in sorted(bib_keys - active_keys):
        errors.append(f"references.bib entry is not an approved manifest record: {key}")

    citations = set(CITATION_PATTERN.findall(manuscript_text))
    for key in sorted(citations - bib_keys):
        errors.append(f"manuscript citation is missing from references.bib: {key}")
    for key in sorted(citations):
        record = records_by_key.get(key)
        if record is not None and record.get("review_status") != "cited":
            errors.append(f"manuscript citation is not marked cited in manifest: {key}")
    for key, record in sorted(records_by_key.items()):
        if record.get("review_status") == "cited" and key not in citations:
            errors.append(f"manifest record marked cited is unused in index.qmd: {key}")
        if key not in entries:
            continue
        locator = record.get("locator", {})
        kind = str(locator.get("type", ""))
        expected = normalize_locator(kind, str(locator.get("value", "")))
        actual = bib_field(entries[key], kind)
        if actual is None:
            errors.append(f"references.bib entry {key} is missing its {kind} locator")
        elif normalize_locator(kind, actual) != expected:
            errors.append(f"references.bib locator does not match manifest for {key}")

    expected_count = None
    if isinstance(collection, dict):
        expected_count = collection.get("top_level_item_count")
    if expected_count != len(records):
        errors.append(
            "collection.top_level_item_count must equal the number of audited records"
        )
    return errors


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root containing index.qmd and references.bib",
    )
    return parser.parse_args()


def main() -> int:
    """Validate the repository and print a compact, actionable result."""
    arguments = parse_arguments()
    errors = validate_repository(arguments.root.resolve())
    if errors:
        for error in errors:
            print(f"bibliography_error={error}")
        return 1

    manifest = load_manifest(
        arguments.root.resolve() / "bibliography" / "zotero-manuscript.json"
    )
    statuses = Counter(record["review_status"] for record in manifest["records"])
    print(
        "bibliography_provenance=accepted "
        f"records={len(manifest['records'])} "
        f"cited={statuses['cited']} approved={statuses['approved']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

