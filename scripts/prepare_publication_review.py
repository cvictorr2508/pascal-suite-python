#!/usr/bin/env python3
"""Audit fixed-budget solver telemetry and stage a publication deposit.

No solver, Git command, network request, or scheduler call is executed.
Input campaigns are read-only. A fresh output directory is required.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import tarfile
from collections import defaultdict
from pathlib import Path

import compare_solver_profile_matrices as comparison
import summarize_refactor28_nested_energy as energy

PROFILES = ("default", "presolve-off", "warm-start")
FIXED_BUDGET_SECONDS = 300.0
ACCEPTED_TERMINAL_STATES = {
    "gurobi": {"OPTIMAL", "TIME_LIMIT"},
    "scip": {"optimal", "timelimit"},
}
ADMIN_KEYS = {
    "command",
    "hostname",
    "python_executable",
    "library_path",
    "proxy_command_fd",
    "proxy_ack_fd",
    "SLURM_JOB_NODELIST",
    "SLURM_NODELIST",
    "SLURM_SUBMIT_DIR",
    "SLURM_JOB_USER",
    "SLURM_JOB_ACCOUNT",
    "account",
    "username",
    "email",
}
SECRET_KEY = re.compile(r"(?i)(password|secret|token|api.?key|license.?file)")
ABS_PATH = re.compile(r"(?:^|\s)(?:/[A-Za-z0-9_.-]+/|[A-Za-z]:[\\/])")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def basename(value):
    return str(value).replace("\\", "/").rsplit("/", 1)[-1]


def finite(value):
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
    )


def clean(value, field=""):
    """Redact administrative strings; preserve scientific finite numbers.

    Non-standard JSON NaN/Infinity becomes a tagged string, never a zero.
    Manual privacy review remains mandatory before public deposit.
    """
    if field in ADMIN_KEYS or SECRET_KEY.search(field):
        return "[redacted]"
    if field == "error" and isinstance(value, dict):
        return {"type": value.get("type"), "message": "[redacted; see audit]"}
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            new_key = basename(key) if ABS_PATH.search(key) else key
            if new_key in result:
                raise ValueError("Redaction would merge distinct dictionary keys")
            result[new_key] = clean(child, key)
        return result
    if isinstance(value, list):
        return [clean(child) for child in value]
    if isinstance(value, float) and not math.isfinite(value):
        return "nonfinite:" + str(value)
    if isinstance(value, str) and ABS_PATH.search(value):
        if value.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", value):
            return basename(value)
        return "[redacted path-bearing text]"
    return value


def write_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            document, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def match_metadata(run, cores, input_index, metadata):
    """Join by configuration and containment, never by filename or list order."""
    matches = []
    start, stop = run.get("start_time"), run.get("stop_time")
    if not finite(start) or not finite(stop) or stop <= start:
        return matches
    for path, item in metadata:
        timestamp = item.get("start_timestamp")
        if (
            item.get("cores") == cores
            and item.get("input_idx") == input_index
            and finite(timestamp)
            and start <= timestamp <= stop
        ):
            matches.append((path, item))
    return matches


def terminal_state(solver, metrics):
    """Return the normalized terminal state recorded by a solver runner."""
    if solver == "gurobi":
        named = metrics.get("status_name")
        if isinstance(named, str):
            return named.upper()
        status = metrics.get("status")
        return {2: "OPTIMAL", 9: "TIME_LIMIT"}.get(status, f"UNKNOWN_{status}")
    return str(metrics.get("status", "unknown")).lower()


def recorded_gap(solver, metrics):
    """Return a recorded solver gap without imputing a missing value."""
    return metrics.get("mip_gap") if solver == "gurobi" else metrics.get("gap")


def quality_reasons(solver, item):
    """Validate provenance without selecting attempts by solution quality.

    The campaigns use a fixed 300-second solve budget. OPTIMAL and TIME_LIMIT
    are both expected terminal states. Outcome metrics remain provenance fields.
    """
    metrics = item.get("metrics", {})
    reasons = []
    if item.get("error"):
        reasons.append("runner_error")
    if terminal_state(solver, metrics) not in ACCEPTED_TERMINAL_STATES[solver]:
        reasons.append("terminal_status_outside_fixed_budget_contract")
    sense = item.get("objective_sense", {})
    if sense.get("requested") != "minimize":
        reasons.append("objective_sense_not_requested_as_minimize")
    if sense.get("effective_name") != "minimize":
        reasons.append("objective_sense_not_effectively_minimize")
    if not finite(metrics.get("objective")):
        reasons.append("objective_missing_or_nonfinite")
    gap = recorded_gap(solver, metrics)
    if gap is not None and (not finite(gap) or gap < 0):
        reasons.append("invalid_recorded_gap")
    return reasons


def audit_campaign(root, solver, required_runs, expected_workloads):
    manifest = read_json(root / "research_manifest.json")
    summary = read_json(root / "profile_matrix_summary.json")
    experiment = manifest["experiment"]
    workloads = [item["path"] for item in manifest["workloads"]]
    if experiment.get("solver") != solver or len(workloads) != expected_workloads:
        raise ValueError(f"{solver}: unexpected solver or workload count")
    resources = experiment["resources"]
    repetitions = experiment["repetitions"]
    if (
        1 not in resources
        or type(repetitions) is not int
        or repetitions < required_runs
    ):
        raise ValueError(f"{solver}: invalid matrix contract")
    if {p["id"] for p in experiment["profiles"]} != set(PROFILES):
        raise ValueError(f"{solver}: unexpected profiles")
    rows, files, problems, sampling = [], [], [], {}
    files.extend(
        [root / "research_manifest.json", root / "profile_matrix_summary.json"]
    )
    for profile in PROFILES:
        folder = root / solver / profile
        telemetry_files = sorted(folder.glob("*_pascal.json"))
        if len(telemetry_files) != 1:
            raise ValueError(f"{solver}/{profile}: expected one telemetry JSON")
        telemetry = read_json(telemetry_files[0])
        base = read_json(folder / "base_config.json")
        if base.get("workloads_list") != workloads:
            raise ValueError(f"{solver}/{profile}: input order mismatch")
        fresh = energy.summarize_document(
            telemetry,
            workloads=workloads,
            required_runs=required_runs,
            required_configurations=len(workloads) * len(resources),
        )
        stored = summary["profiles"][profile]["energy"]
        valid = {item["run"]: item for item in fresh["runs"]}
        if valid != {item["run"]: item for item in stored["runs"]}:
            raise ValueError(
                f"{solver}/{profile}: stale run measurements or validity summary"
            )
        invalid = {item["run"]: item["reasons"] for item in fresh["invalid_runs"]}
        expected_keys = {
            f"{c};{i};{r}"
            for c in resources
            for i in range(len(workloads))
            for r in range(1, repetitions + 1)
        }
        if set(telemetry["data"]) != expected_keys:
            raise ValueError(f"{solver}/{profile}: unexpected attempt identities")
        if not fresh["accuracy"]["accepted"]:
            problems.append(f"{solver}/{profile}: telemetry gate failed")
        metadata = [(p, read_json(p)) for p in sorted(folder.glob("meta_*.json"))]
        used = set()
        if len(metadata) != len(expected_keys):
            problems.append(f"{solver}/{profile}: metadata count mismatch")
        files.extend(
            [telemetry_files[0], folder / "base_config.json", folder / "summary.json"]
        )
        files.extend(path for path, _ in metadata)
        periods = [item["sample_period_s"] for item in fresh["runs"]]
        sampling[profile] = {
            "configured_sample_rate": telemetry.get("config", {}).get("sample_rate"),
            "effective_period_median_s": statistics.median(periods),
            "effective_period_min_s": min(periods),
            "effective_period_max_s": max(periods),
            "sensor": fresh["sensor_name"],
            "domain": fresh["global_domain"],
        }
        for key, run in sorted(telemetry["data"].items()):
            cores, index, repetition = energy.parse_run_key(key)
            matches = match_metadata(run, cores, index, metadata)
            item, name, reasons = {}, None, []
            if len(matches) != 1:
                reasons.append("metadata_join_not_unique")
            else:
                path, item = matches[0]
                name = path.name
                if name in used:
                    reasons.append("metadata_reused")
                used.add(name)
                if (
                    item.get("solver") != solver
                    or item.get("profile", {}).get("id") != profile
                    or item.get("workload") != workloads[index]
                ):
                    reasons.append("metadata_identity_mismatch")
            if reasons:
                problems.append(f"{solver}/{profile}/{key}: {','.join(reasons)}")
            reasons.extend(quality_reasons(solver, item))
            included = key in valid and cores == 1
            if included and reasons:
                problems.append(f"{solver}/{profile}/{key}: quality failure")
            metrics = item.get("metrics", {})
            start = item.get("initial_solution", {})
            if included and profile == "warm-start":
                if start.get("applied") is not True:
                    reasons.append("start_not_applied")
                    problems.append(f"{solver}/{profile}/{key}: start not applied")
                if solver == "scip" and start.get("accepted") is not True:
                    reasons.append("scip_start_not_accepted")
                    problems.append(f"{solver}/{profile}/{key}: start not accepted")
            regional = valid.get(key, {}).get("regions", {})
            row = {
                "solver": solver,
                "profile": profile,
                "workload": basename(workloads[index]),
                "cores": cores,
                "repetition": repetition,
                "run": key,
                "metadata_file": name,
                "energy_valid": key in valid,
                "included_one_core": included,
                "terminal_state": terminal_state(solver, metrics),
                "status": metrics.get("status"),
                "objective": metrics.get("objective"),
                "best_bound": metrics.get("best_bound"),
                "gap": recorded_gap(solver, metrics),
                "node_count": metrics.get("node_count"),
                "start_applied": start.get("applied"),
                "start_accepted": start.get("accepted"),
                "quality_reasons": reasons,
                "telemetry_reasons": invalid.get(key, []),
                "sample_period_s": valid.get(key, {}).get("sample_period_s"),
            }
            for region in ("0", "0.1", "0.2"):
                for field in ("duration_s", "energy_j"):
                    row[f"region_{region}_{field}"] = regional.get(region, {}).get(
                        field
                    )
            rows.append(row)
        if len(used) != len(metadata):
            problems.append(f"{solver}/{profile}: unmatched metadata")
    environment = {
        "source": manifest.get("source"),
        "runtime": manifest.get("runtime"),
        "slurm": manifest.get("slurm"),
        "sampling": sampling,
        "not_established_by_partition_label": [
            "CPU model",
            "socket count",
            "frequency policy",
            "physical RAPL subdomains",
            "idle subtraction",
        ],
        "warning": (
            "Do not substitute a current login-node inventory for historical "
            "execution hardware."
        ),
    }
    return rows, files, problems, environment


def fixed_budget_pairs(rows, required_runs=5):
    """Audit paired coverage without comparing solver objective values.

    Cross-solver objective equality is not an acceptance rule for runs that may
    terminate at the common time budget with different incumbents and bounds.
    """
    grouped = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row["included_one_core"]:
            grouped[(row["profile"], row["workload"])][row["solver"]].append(row)
    pairs = []
    for (profile, workload), groups in sorted(grouped.items()):
        enough = all(len(groups[s]) >= required_runs for s in ("gurobi", "scip"))
        clean_runs = not any(
            row["quality_reasons"] for group in groups.values() for row in group
        )
        solver_summaries = {}
        for solver in ("gurobi", "scip"):
            objectives = [row["objective"] for row in groups[solver]]
            states = defaultdict(int)
            for row in groups[solver]:
                states[row["terminal_state"]] += 1
            solver_summaries[solver] = {
                "valid_runs": len(groups[solver]),
                "terminal_states": dict(sorted(states.items())),
                "objective_min": min(objectives) if objectives else None,
                "objective_median": statistics.median(objectives)
                if objectives
                else None,
                "objective_max": max(objectives) if objectives else None,
            }
        accepted = enough and clean_runs
        pairs.append(
            {
                "profile": profile,
                "workload": workload,
                "required_valid_runs_per_solver": required_runs,
                "solver_summaries": solver_summaries,
                "outcome_metrics_used_for_selection": False,
                "accepted": accepted,
            }
        )
    return pairs


def prepare(
    gurobi_root,
    scip_root,
    output_dir,
    *,
    required_runs=5,
    expected_workloads=5,
    privacy_reviewed=False,
    authorship_reviewed=False,
    hardware_reviewed=False,
):
    roots = {"gurobi": gurobi_root.resolve(), "scip": scip_root.resolve()}
    output_dir = output_dir.resolve()
    archive = output_dir.parent / (output_dir.name + ".tar.gz")
    if (
        output_dir.exists()
        or archive.exists()
        or any(output_dir.is_relative_to(r) for r in roots.values())
    ):
        raise ValueError("Output must be a NEW directory outside both input campaigns")
    rows, inputs, problems, environments = [], [], [], {}
    for solver, root in roots.items():
        records, paths, errors, environment = audit_campaign(
            root, solver, required_runs, expected_workloads
        )
        rows.extend(records)
        problems.extend(errors)
        environments[solver] = environment
        for path in paths:
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError("Input artifact escapes campaign directory")
            inputs.append((path, Path("campaigns") / solver / path.relative_to(root)))
    paired = fixed_budget_pairs(rows, required_runs)
    legacy = comparison.build_comparison(roots["gurobi"], roots["scip"])
    accepted = (
        not problems
        and len(paired) == expected_workloads * 3
        and all(p["accepted"] for p in paired)
        and legacy["gate"]["accepted"] is True
    )
    manual_reviews = {
        "privacy_and_file_review": bool(privacy_reviewed),
        "dataset_authorship_review": bool(authorship_reviewed),
        "historical_hardware_review": bool(hardware_reviewed),
    }
    blocker_labels = {
        "privacy_and_file_review": "Manual privacy and file review",
        "dataset_authorship_review": "Dataset authorship review",
        "historical_hardware_review": "Historical hardware documentation review",
    }
    blockers = [
        blocker_labels[name] for name, done in manual_reviews.items() if not done
    ]
    publication_ready = accepted and not blockers
    report = {
        "schema_version": 2,
        "quality_audit_accepted": accepted,
        "publication_ready": publication_ready,
        "publication_blockers": blockers,
        "manual_reviews": manual_reviews,
        "policy": {
            "required_valid_runs_per_solver": required_runs,
            "solver_time_limit_s": FIXED_BUDGET_SECONDS,
            "accepted_terminal_states": {
                solver: sorted(states)
                for solver, states in ACCEPTED_TERMINAL_STATES.items()
            },
            "outcome_metrics_used_for_selection": False,
            "meaning": (
                "Fixed-budget telemetry audit; outcome metadata is provenance only"
            ),
            "missing_gap": "Unknown, never imputed as zero",
            "gurobi_start_acceptance": "Not established by historical applied flag",
            "metadata_join": (
                "Configuration plus start timestamp within Analyzer interval"
            ),
        },
        "attempts": len(rows),
        "paired_configurations": len(paired),
        "missing_gap_included_runs": sum(
            r["included_one_core"] and r["gap"] is None for r in rows
        ),
        "problems": problems,
        "pairs": paired,
        "rows": rows,
    }
    output_dir.mkdir(parents=True)
    write_json(output_dir / "publication_audit.json", clean(report))
    write_json(output_dir / "environment_inventory.json", clean(environments))
    with (output_dir / "run_quality.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(clean(rows))
    comparison.write_evidence(clean(legacy), output_dir / "comparison")
    inventory = []
    for source, relative in inputs:
        before = sha256(source)
        target = output_dir / relative
        write_json(target, clean(read_json(source)))
        if sha256(source) != before:
            raise ValueError("Input changed during export; discard this draft output")
        inventory.append(
            {
                "path": relative.as_posix(),
                "original_sha256": before,
                "distributed_sha256": sha256(target),
            }
        )
    write_json(output_dir / "artifact_inventory.json", inventory)
    for name in (
        "prepare_publication_review.py",
        "summarize_refactor28_nested_energy.py",
        "summarize_solver_profile_matrix.py",
        "compare_solver_profile_matrices.py",
    ):
        target = output_dir / "scripts" / name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(Path(__file__).with_name(name).read_bytes())
    readme_title = "# PaScal telemetry evidence"
    if not publication_ready:
        readme_title += " - REVIEW DRAFT"
    readme_body = """This is a sanitized derivative, not a bit-identical raw
archive. Original campaigns remain unchanged. No benchmark instances, solver
libraries, solver license files, start files, or arbitrary logs are included.
The dataset and reconstruction scripts use the MIT License included as LICENSE.

campaigns/ contains Analyzer JSON for all attempts, runner metadata, base
configurations, manifests, and summaries. Administrative host/path/command
fields are redacted; absolute paths become basenames; free-form runner errors
are redacted. Nonfinite JSON constants become nonfinite:<value> strings, not
corrected measurements. artifact_inventory.json links each original hash to its
distributed hash. Manually inspect before upload.

## Data dictionary

Analyzer run keys are cores;input_index;repetition. Sensor rows are
[power_W, Unix_time_s]. Region 0 is the pipeline; 0.1 is read/API model load;
0.2 is the optimize call. Energy is joules, duration seconds, and EDP
joule-seconds. run_quality.csv retains all attempts; only energy_valid and
included_one_core rows support the paired quality audit. objective is in the
benchmark's objective units; gap is fractional when recorded. Missing values
mean unknown, never zero.

Gurobi OPTIMAL/TIME_LIMIT and SCIP optimal/timelimit are valid terminal states
under the shared 300-second fixed-budget contract. Objective, bound, gap,
status, and node count are provenance only and never select attempts.
Cross-solver objective equality is not required. Sampling periods come from
accepted telemetry runs.

## Reconstruct (Python 3.10+, standard library only)

```bash
sha256sum -c SHA256SUMS
python scripts/summarize_solver_profile_matrix.py campaigns/gurobi \
    --require-runs 5 --require-configurations 15
python scripts/summarize_solver_profile_matrix.py campaigns/scip \
    --require-runs 5 --require-configurations 5
python scripts/compare_solver_profile_matrices.py \
    --gurobi-root campaigns/gurobi \
    --scip-root campaigns/scip \
    --output-dir reconstructed_comparison
```

The summaries reconstructed after path sanitization have new hashes. Compare
scientific fields, not byte identity with historical reports. Reconstruction
writes new profile summaries: work on a copy of this archive.
publication_audit.json records the explicit manual-review approvals supplied at
export. Files, privacy transformations, dataset authorship, and historical
hardware evidence must all be approved before publication_ready becomes true.
Exact CPU/domain information cannot be inferred from a partition name.
"""
    (output_dir / "README.md").write_text(
        readme_title + "\n\n" + readme_body,
        encoding="utf-8",
        newline="\n",
    )
    (output_dir / "LICENSE").write_bytes(
        Path(__file__).resolve().parents[1].joinpath("LICENSE").read_bytes()
    )
    (output_dir / "scripts" / "LICENSE").write_bytes(
        Path(__file__).resolve().parents[1].joinpath("LICENSE").read_bytes()
    )
    distributed = sorted(p for p in output_dir.rglob("*") if p.is_file())
    (output_dir / "SHA256SUMS").write_text(
        "".join(
            f"{sha256(p)}  {p.relative_to(output_dir).as_posix()}\n"
            for p in distributed
        ),
        encoding="utf-8",
        newline="\n",
    )
    with tarfile.open(archive, "x:gz") as stream:
        for path in sorted(output_dir.rglob("*")):
            if path.is_file():
                stream.add(
                    path,
                    arcname=(
                        Path(output_dir.name) / path.relative_to(output_dir)
                    ).as_posix(),
                    recursive=False,
                )
    return report, archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gurobi-root", type=Path, required=True)
    parser.add_argument("--scip-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--privacy-reviewed", action="store_true")
    parser.add_argument("--authorship-reviewed", action="store_true")
    parser.add_argument("--hardware-reviewed", action="store_true")
    args = parser.parse_args()
    try:
        report, archive = prepare(
            args.gurobi_root,
            args.scip_root,
            args.output_dir,
            privacy_reviewed=args.privacy_reviewed,
            authorship_reviewed=args.authorship_reviewed,
            hardware_reviewed=args.hardware_reviewed,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"preparation_error={error}")
        return 2
    print(f"attempts={report['attempts']}")
    print(f"paired_configurations={report['paired_configurations']}")
    print(f"quality_audit_accepted={report['quality_audit_accepted']}")
    print(f"publication_ready={report['publication_ready']}")
    if report["publication_blockers"]:
        print(f"publication_blockers={report['publication_blockers']}")
    print(f"audit={args.output_dir / 'publication_audit.json'}")
    print(f"archive={archive}")
    print(f"archive_sha256={sha256(archive)}")
    return 0 if report["quality_audit_accepted"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
