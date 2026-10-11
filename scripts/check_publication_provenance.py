#!/usr/bin/env python3
"""Check frozen result generations offline, without solver or network imports."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATION = "corrected-minimize-300s-v2"
SOURCE_COMMIT = "fbbf7d7178e022ff8cf759d8fd7568359b583cf8"
PROFILES = ("default", "presolve-off", "warm-start")
WORKLOADS = tuple(f"CFL_hard_instance_{i}.lp.gz" for i in (5, 10, 15, 20, 25))
RATIO_FIELDS = (
    "scip_to_gurobi_duration_ratio",
    "scip_to_gurobi_energy_ratio",
    "scip_to_gurobi_edp_ratio",
)
MEASUREMENT_FIELDS = (
    "median_solve_duration_s",
    "median_solve_energy_j",
    "median_solve_edp_js",
)
GATE_KEYS = {
    "accepted",
    "common_one_core_configurations_complete",
    "dataset_fingerprints_match",
    "effective_objective_sense_match",
    "exclusive_allocation_verified",
    "input_matrices_accepted",
    "performance_comparison_eligible",
    "profile_contract_matches",
    "same_partition",
    "source_worktrees_clean",
    "time_budget_match",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def positive(value: str) -> float:
    number = float(value)
    require(math.isfinite(number) and number > 0, f"invalid measurement: {value}")
    return number


def unique_rows(rows: list[dict], columns: tuple[str, ...]) -> dict:
    indexed = {tuple(row[column] for column in columns): row for row in rows}
    require(len(indexed) == len(rows), f"duplicate keys: {columns}")
    return indexed


def table_cells(document: str) -> list[list[str]]:
    return [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in document.splitlines()
        if line.lstrip().startswith("|")
    ]


def normalized(label: str) -> str:
    return label.lower().replace("-", " ")


def validate_snapshot(snapshot: dict) -> dict:
    """Reconcile processed records, not the inaccessible raw physical attempts."""
    provenance = snapshot["provenance"]
    require(provenance["generation_id"] == GENERATION, "wrong generation")
    require(provenance["campaign_source_commit"] == SOURCE_COMMIT, "wrong source")
    require(provenance["submission_id"] == "36682", "wrong submission")
    contract = provenance["contract"]
    require(contract["objective_sense"] == "minimize", "wrong objective direction")
    require(contract["solver_time_limit_s"] == 300, "wrong solver budget")
    require(contract["region_id"] == "0.2", "wrong comparison region")
    require(contract["profiles"] == list(PROFILES), "wrong profile contract")
    require(contract["paired_resources"] == [1], "comparison is not one-core")
    require(
        set(provenance["gate"]) == GATE_KEYS
        and all(value is True for value in provenance["gate"].values()),
        "comparison gate did not pass",
    )
    require(
        provenance["dataset_version_doi"] == "10.5281/zenodo.23071850",
        "wrong dataset version",
    )
    require(
        provenance["software_version_doi"] == "10.5281/zenodo.23082727",
        "wrong software version",
    )
    for solver, resources in (("gurobi", [1, 2, 4]), ("scip", [1])):
        source = provenance["inputs"][solver]
        require(source["source"]["git_commit"] == SOURCE_COMMIT, "input source drift")
        require(source["source"]["tracked_worktree_clean"] is True, "dirty source")
        require(source["resources"] == resources, "wrong resource matrix")
        require(source["repetitions"] == 6, "wrong repetition contract")
        allocation = source["allocation"]
        require(
            allocation["partition"] == "intel-128"
            and allocation["requested_mode"] == "exclusive"
            and allocation["scheduler_oversubscribe"] == "NO",
            "allocation contract drift",
        )

    measurements = unique_rows(
        snapshot["measurements"], ("solver", "profile", "workload", "cores")
    )
    expected = {
        (solver, profile, workload, str(cores))
        for solver, resources in (("gurobi", (1, 2, 4)), ("scip", (1,)))
        for profile, workload, cores in itertools.product(
            PROFILES, WORKLOADS, resources
        )
    }
    require(set(measurements) == expected, "incomplete configuration coverage")
    for row in measurements.values():
        require(5 <= int(row["valid_run_count"]) <= 6, "under-replicated configuration")
        for field in MEASUREMENT_FIELDS:
            positive(row[field])

    validity = unique_rows(snapshot["validity"], ("solver", "profile"))
    require(
        set(validity) == set(itertools.product(("gurobi", "scip"), PROFILES)),
        "incomplete validity matrix",
    )
    for (solver, profile), row in validity.items():
        selected = [
            m for key, m in measurements.items() if key[:2] == (solver, profile)
        ]
        valid = sum(int(m["valid_run_count"]) for m in selected)
        attempted = len(selected) * 6
        require(int(row["attempted_runs"]) == attempted, "attempt count mismatch")
        require(int(row["valid_runs"]) == valid, "valid count mismatch")
        require(int(row["invalid_runs"]) == attempted - valid, "invalid count mismatch")
        require(int(row["configurations"]) == len(selected), "configuration mismatch")
        require(row["accepted"] == "true", "mandatory validity gate failed")
        require(
            positive(row["median_energy_error_percent"]) <= 5, "accuracy gate failed"
        )
        positive(row["max_cv_percent"])
    counts = provenance["counts"]
    require(
        sum(int(r["attempted_runs"]) for r in validity.values())
        == counts["logical_attempts"]
        == 360,
        "logical attempt total mismatch",
    )
    require(
        sum(int(r["valid_runs"]) for r in validity.values())
        == counts["valid_logical_attempts"]
        == 336,
        "valid attempt total mismatch",
    )
    require(
        sum(int(r["invalid_runs"]) for r in validity.values())
        == counts["invalid_logical_attempts"]
        == 24,
        "invalid attempt total mismatch",
    )
    retry = provenance["retry"]
    require(
        counts["physical_attempts_reported"]
        == counts["logical_attempts"] + retry["physical_retry_attempts"]
        == 362,
        "reported physical/logical count mismatch",
    )
    require(
        retry["distributed_composition_manifest_present"] is False
        and retry["full_physical_chain_independently_verified"] is False,
        "unresolved archival chain incorrectly certified",
    )

    pairs = unique_rows(snapshot["pairs"], ("profile", "workload", "cores"))
    require(
        set(pairs) == set(itertools.product(PROFILES, WORKLOADS, ("1",))),
        "incomplete paired coverage",
    )
    require(len(pairs) == counts["paired_configurations"] == 15, "pair count mismatch")
    for (profile, workload, cores), row in pairs.items():
        gurobi = measurements[("gurobi", profile, workload, cores)]
        scip = measurements[("scip", profile, workload, cores)]
        for solver, measurement in (("gurobi", gurobi), ("scip", scip)):
            require(
                row[f"{solver}_valid_run_count"] == measurement["valid_run_count"],
                "paired replication count mismatch",
            )
        for field, metric in zip(RATIO_FIELDS, MEASUREMENT_FIELDS, strict=True):
            require(
                math.isclose(
                    positive(row[field]),
                    positive(scip[metric]) / positive(gurobi[metric]),
                    rel_tol=1e-12,
                ),
                f"paired ratio mismatch: {profile}/{workload}/{field}",
            )
    aggregates = unique_rows(snapshot["aggregates"], ("profile",))
    require(set(aggregates) == {(p,) for p in PROFILES}, "incomplete profile summary")
    for (profile,), row in aggregates.items():
        require(int(row["paired_configurations"]) == 5, "wrong per-profile pair count")
        selected = [p for key, p in pairs.items() if key[0] == profile]
        for field in RATIO_FIELDS:
            median = statistics.median(positive(p[field]) for p in selected)
            require(
                row[f"median_{field}"] == f"{median:.6f}", "profile median mismatch"
            )

    for name, document in snapshot["documents"].items():
        cells = table_cells(document)
        for (solver, profile), row in validity.items():
            matches = [
                r
                for r in cells
                if len(r) == 5
                and normalized(r[0]) == solver
                and normalized(r[1]) == normalized(profile)
            ]
            require(len(matches) == 1, f"missing/duplicate validity row in {name}")
            require(
                matches[0][2:]
                == [
                    f"{row['valid_runs']} / {row['attempted_runs']}",
                    row["median_energy_error_percent"],
                    row["max_cv_percent"],
                ],
                f"validity table drift: {name}",
            )
        for (profile,), row in aggregates.items():
            matches = [
                r
                for r in cells
                if len(r) == 4 and normalized(r[0]) == normalized(profile)
            ]
            require(len(matches) == 1, f"missing/duplicate comparison row in {name}")
            require(
                matches[0][1:] == [row[f"median_{f}"] for f in RATIO_FIELDS],
                f"comparison table drift: {name}",
            )
    return {
        "consistency_accepted": True,
        "generation": GENERATION,
        "configurations": len(measurements),
        "paired_configurations": len(pairs),
        "logical_attempts": 360,
        "archival_chain_complete": False,
        "retry_parameter_equivalence_checked": False,
        "preferred_cv_exceedances": [
            f"{s}/{p}"
            for (s, p), r in validity.items()
            if float(r["max_cv_percent"]) > 10
        ],
    }


def load_snapshot(root: Path) -> dict:
    registry = json.loads((root / "publication/result-generations.json").read_text())
    require(
        registry["submitted_generation"] == GENERATION, "wrong submitted generation"
    )
    generations = registry["generations"]
    require(
        [g["id"] for g in generations]
        == ["historical-source-sense-20260911", GENERATION],
        "generation registry drift",
    )
    for generation in generations:
        expected_names = {
            "profile-matrix-validity.csv",
            "controlled-one-core-comparison.csv",
            "provenance.json",
        }
        if generation["id"] == GENERATION:
            expected_names |= {
                "solver_measurements.csv",
                "paired_one_core_comparisons.csv",
            }
        require(
            set(generation["files"])
            == {f"{generation['directory']}/{name}" for name in expected_names},
            "incomplete checksum coverage",
        )
        for filename, expected in generation["files"].items():
            path = (root / filename).resolve()
            require(path.is_relative_to(root.resolve()), "unsafe artifact path")
            require(
                hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                f"checksum mismatch: {filename}",
            )
    directory = root / generations[1]["directory"]

    def read_csv(name: str) -> list[dict]:
        with (directory / name).open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    return {
        "provenance": json.loads((directory / "provenance.json").read_text()),
        "validity": read_csv("profile-matrix-validity.csv"),
        "measurements": read_csv("solver_measurements.csv"),
        "pairs": read_csv("paired_one_core_comparisons.csv"),
        "aggregates": read_csv("controlled-one-core-comparison.csv"),
        "documents": {
            name: (root / name).read_text(encoding="utf-8")
            for name in ("docs/research-mvp.md", "index.qmd")
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--submission-pdf", type=Path)
    parser.add_argument("--submission-html", type=Path)
    args = parser.parse_args()
    try:
        result = validate_snapshot(load_snapshot(args.root))
        registry = json.loads(
            (args.root / "publication/result-generations.json").read_text()
        )
        for kind in ("pdf", "html"):
            path = getattr(args, f"submission_{kind}")
            if path is not None:
                require(
                    hashlib.sha256(path.read_bytes()).hexdigest()
                    == registry["submission"][f"{kind}_sha256"],
                    f"submitted {kind} hash mismatch",
                )
                result[f"submission_{kind}_verified"] = True
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"publication_provenance=failed reason={error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
