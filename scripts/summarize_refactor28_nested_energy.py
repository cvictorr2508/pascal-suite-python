#!/usr/bin/env python3
"""Validate sampled RAPL energy for the canonical nested solver regions."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any


REQUIRED_REGION_IDS = ("0", "0.1", "0.2")


class EnergySummaryError(ValueError):
    """Raised when an Analyzer document cannot support the validation."""


def parse_run_key(run_key: Any) -> tuple[int, int, int]:
    """Return ``(cores, input_index, repetition)`` from an Analyzer run key."""
    parts = str(run_key).split(";")
    if len(parts) != 3:
        raise EnergySummaryError(
            f"run key {run_key!r} must use cores;input;repetition"
        )
    try:
        cores, input_index, repetition = (int(part) for part in parts)
    except ValueError as exc:
        raise EnergySummaryError(
            f"run key {run_key!r} must contain integer fields"
        ) from exc
    if cores < 1 or input_index < 0 or repetition < 1:
        raise EnergySummaryError(f"run key {run_key!r} contains invalid values")
    return cores, input_index, repetition


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EnergySummaryError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise EnergySummaryError(f"{label} must be finite")
    return result


def normalize_power_samples(
    raw_samples: Any,
) -> tuple[list[tuple[float, float]], float]:
    if not isinstance(raw_samples, list):
        raise EnergySummaryError("sampled RAPL data must be a list")

    samples: list[tuple[float, float]] = []
    for index, sample in enumerate(raw_samples):
        if not isinstance(sample, (list, tuple)) or len(sample) < 2:
            raise EnergySummaryError(f"invalid power sample at index {index}")
        power = _number(sample[0], f"sample[{index}].power")
        timestamp = _number(sample[1], f"sample[{index}].timestamp")
        if power < 0:
            raise EnergySummaryError(f"sample[{index}].power must be non-negative")
        samples.append((power, timestamp))

    samples.sort(key=lambda item: item[1])
    unique: list[tuple[float, float]] = []
    for sample in samples:
        if unique and unique[-1][1] == sample[1]:
            unique[-1] = sample
        else:
            unique.append(sample)

    if len(unique) < 2:
        raise EnergySummaryError("at least two distinct power samples are required")

    gaps = [
        right[1] - left[1]
        for left, right in zip(unique, unique[1:])
    ]
    if any(gap <= 0 for gap in gaps):
        raise EnergySummaryError("power sample timestamps must increase")

    sample_period = statistics.median(gaps)
    if any(gap > sample_period * 3 for gap in gaps):
        raise EnergySummaryError("power samples contain a gap over three periods")

    return unique, sample_period


def merge_region_intervals(raw_intervals: Any) -> list[tuple[float, float]]:
    if not isinstance(raw_intervals, list) or not raw_intervals:
        raise EnergySummaryError("region must contain at least one interval")

    intervals: list[tuple[float, float]] = []
    for index, interval in enumerate(raw_intervals):
        if not isinstance(interval, (list, tuple)) or len(interval) < 2:
            raise EnergySummaryError(f"invalid region interval at index {index}")
        start = _number(interval[0], f"region[{index}].start_time")
        stop = _number(interval[1], f"region[{index}].stop_time")
        if stop < start:
            raise EnergySummaryError(f"region interval {index} stops before it starts")
        intervals.append((start, stop))

    intervals.sort(key=lambda item: item[0])
    merged: list[tuple[float, float]] = []
    for start, stop in intervals:
        if not merged or start > merged[-1][1]:
            merged.append((start, stop))
            continue
        previous_start, previous_stop = merged[-1]
        merged[-1] = (previous_start, max(previous_stop, stop))
    return merged


def integrate_sampled_power(
    samples: list[tuple[float, float]],
    sample_period: float,
    intervals: list[tuple[float, float]],
) -> tuple[float, float]:
    first_timestamp = samples[0][1]
    last_timestamp = samples[-1][1]
    if any(
        start < first_timestamp - sample_period
        or stop > last_timestamp + sample_period
        for start, stop in intervals
    ):
        raise EnergySummaryError("power samples do not cover an integration interval")

    def power_at(timestamp: float) -> float:
        if timestamp <= first_timestamp:
            return samples[0][0]
        if timestamp >= last_timestamp:
            return samples[-1][0]

        low = 0
        high = len(samples) - 1
        while high - low > 1:
            candidate = (low + high) // 2
            if samples[candidate][1] <= timestamp:
                low = candidate
            else:
                high = candidate

        left_power, left_time = samples[low]
        right_power, right_time = samples[high]
        ratio = (timestamp - left_time) / (right_time - left_time)
        return left_power + (right_power - left_power) * ratio

    energy = 0.0
    duration = 0.0
    sample_timestamps = [timestamp for _, timestamp in samples]
    for start, stop in intervals:
        knots = [
            start,
            *(timestamp for timestamp in sample_timestamps if start < timestamp < stop),
            stop,
        ]
        for left, right in zip(knots, knots[1:]):
            energy += (power_at(left) + power_at(right)) * (right - left) / 2
        duration += stop - start

    return energy, duration


def _series_statistics(values: list[float]) -> dict[str, float]:
    mean = statistics.fmean(values)
    standard_deviation = statistics.stdev(values) if len(values) > 1 else 0.0
    cv_percent = standard_deviation / mean * 100 if mean else 0.0
    return {
        "mean_j": mean,
        "median_j": statistics.median(values),
        "standard_deviation_j": standard_deviation,
        "cv_percent": cv_percent,
    }


def summarize_document(
    document: Any,
    *,
    sensor_name: str = "rapl_sample-sysfs",
    global_domain: str = "rapl-sysfs",
    required_runs: int = 5,
    max_median_error_percent: float = 5.0,
    preferred_max_cv_percent: float = 10.0,
    workloads: list[str] | None = None,
    required_configurations: int | None = None,
) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise EnergySummaryError("JSON root must be an object")
    data = document.get("data")
    if not isinstance(data, dict) or not data:
        raise EnergySummaryError("JSON must contain non-empty data")

    valid_run_keys: list[str] = []
    invalid_runs: list[dict[str, Any]] = []
    for run_key in sorted(data):
        configuration: dict[str, int] | None = None
        reasons: list[str] = []
        try:
            cores, input_index, repetition = parse_run_key(run_key)
            configuration = {
                "cores": cores,
                "input_index": input_index,
                "repetition": repetition,
            }
        except EnergySummaryError as exc:
            reasons.append(str(exc))

        run = data[run_key]
        if not isinstance(run, dict):
            reasons.append(f"run {run_key} must be an object")
        else:
            try:
                global_energy = _number(
                    run.get(global_domain),
                    f"run {run_key}.{global_domain}",
                )
                if global_energy <= 0:
                    raise EnergySummaryError(
                        f"run {run_key} global energy must be positive"
                    )
            except EnergySummaryError as exc:
                reasons.append(str(exc))

            try:
                sensors = run.get("sensors")
                if not isinstance(sensors, dict) or sensor_name not in sensors:
                    raise EnergySummaryError(
                        f"run {run_key} lacks sensor {sensor_name}"
                    )
                normalize_power_samples(sensors[sensor_name])
            except EnergySummaryError as exc:
                reasons.append(str(exc))

        if reasons:
            invalid_runs.append(
                {
                    "run": str(run_key),
                    "configuration": configuration,
                    "reasons": reasons,
                }
            )
        else:
            valid_run_keys.append(run_key)

    if not valid_run_keys:
        details = "; ".join(
            reason
            for invalid_run in invalid_runs
            for reason in invalid_run["reasons"]
        )
        raise EnergySummaryError(f"JSON contains no valid energy runs: {details}")

    runs: list[dict[str, Any]] = []
    for run_key in valid_run_keys:
        try:
            cores, input_index, repetition = parse_run_key(run_key)
            run = data[run_key]
            if not isinstance(run, dict):
                raise EnergySummaryError(f"run {run_key} must be an object")

            start_time = _number(run.get("start_time"), f"run {run_key}.start_time")
            stop_time = _number(run.get("stop_time"), f"run {run_key}.stop_time")
            if stop_time <= start_time:
                raise EnergySummaryError(f"run {run_key} has a non-positive duration")

            global_energy = _number(
                run.get(global_domain),
                f"run {run_key}.{global_domain}",
            )
            if global_energy <= 0:
                raise EnergySummaryError(f"run {run_key} global energy must be positive")

            sensors = run.get("sensors")
            if not isinstance(sensors, dict) or sensor_name not in sensors:
                raise EnergySummaryError(f"run {run_key} lacks sensor {sensor_name}")
            samples, sample_period = normalize_power_samples(sensors[sensor_name])

            whole_energy, whole_duration = integrate_sampled_power(
                samples,
                sample_period,
                [(start_time, stop_time)],
            )
            whole_error = abs(whole_energy - global_energy) / global_energy * 100

            raw_regions = run.get("regions")
            if not isinstance(raw_regions, dict):
                raise EnergySummaryError(f"run {run_key} lacks regions")

            region_summaries: dict[str, dict[str, float]] = {}
            for region_id in REQUIRED_REGION_IDS:
                if region_id not in raw_regions:
                    raise EnergySummaryError(
                        f"run {run_key} lacks canonical region {region_id}"
                    )
                intervals = merge_region_intervals(raw_regions[region_id])
                energy, duration = integrate_sampled_power(
                    samples,
                    sample_period,
                    intervals,
                )
                if energy <= 0:
                    raise EnergySummaryError(
                        f"run {run_key} region {region_id} energy must be positive"
                    )
                region_summaries[region_id] = {
                    "duration_s": duration,
                    "energy_j": energy,
                }

            root_duration = region_summaries["0"]["duration_s"]
            root_coverage_percent = root_duration / whole_duration * 100
            children_duration = (
                region_summaries["0.1"]["duration_s"]
                + region_summaries["0.2"]["duration_s"]
            )

            runs.append(
                {
                    "run": str(run_key),
                    "configuration": {
                        "cores": cores,
                        "input_index": input_index,
                        "repetition": repetition,
                        "workload": (
                            workloads[input_index]
                            if workloads is not None and input_index < len(workloads)
                            else None
                        ),
                    },
                    "sample_count": len(samples),
                    "sample_period_s": sample_period,
                    "whole_program": {
                        "duration_s": whole_duration,
                        "global_energy_j": global_energy,
                        "sampled_energy_j": whole_energy,
                        "absolute_error_percent": whole_error,
                    },
                    "regions": region_summaries,
                    "root_coverage_percent": root_coverage_percent,
                    "root_children_duration_gap_s": abs(
                        root_duration - children_duration
                    ),
                }
            )

        except EnergySummaryError as exc:
            cores, input_index, repetition = parse_run_key(run_key)
            invalid_runs.append(
                {
                    "run": str(run_key),
                    "configuration": {
                        "cores": cores,
                        "input_index": input_index,
                        "repetition": repetition,
                    },
                    "reasons": [str(exc)],
                }
            )

    if not runs:
        details = "; ".join(
            reason
            for invalid_run in invalid_runs
            for reason in invalid_run["reasons"]
        )
        raise EnergySummaryError(
            f"JSON contains no integrable energy runs: {details}"
        )

    grouped_runs: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for run in runs:
        configuration = run["configuration"]
        key = (configuration["cores"], configuration["input_index"])
        grouped_runs.setdefault(key, []).append(run)

    configuration_groups: list[dict[str, Any]] = []
    for (cores, input_index), group_runs in sorted(grouped_runs.items()):
        group_errors = [
            run["whole_program"]["absolute_error_percent"]
            for run in group_runs
        ]
        group_regional_statistics = {
            region_id: _series_statistics(
                [run["regions"][region_id]["energy_j"] for run in group_runs]
            )
            for region_id in REQUIRED_REGION_IDS
        }
        group_run_count_accepted = len(group_runs) >= required_runs
        group_median_error = statistics.median(group_errors)
        group_root_cv = group_regional_statistics["0"]["cv_percent"]
        workload = group_runs[0]["configuration"]["workload"]
        configuration_groups.append(
            {
                "cores": cores,
                "input_index": input_index,
                "workload": workload,
                "workload_name": Path(workload).name if workload else None,
                "run_count": len(group_runs),
                "required_runs": required_runs,
                "accuracy": {
                    "median_absolute_error_percent": group_median_error,
                    "mean_absolute_error_percent": statistics.fmean(group_errors),
                    "maximum_absolute_error_percent": max(group_errors),
                    "threshold_percent": max_median_error_percent,
                    "accepted": group_run_count_accepted
                    and group_median_error <= max_median_error_percent,
                },
                "variability": {
                    "region_0_cv_percent": group_root_cv,
                    "preferred_threshold_percent": preferred_max_cv_percent,
                    "preferred": group_run_count_accepted
                    and group_root_cv <= preferred_max_cv_percent,
                },
                "regional_energy_statistics": group_regional_statistics,
            }
        )

    errors = [run["whole_program"]["absolute_error_percent"] for run in runs]
    global_energies = [run["whole_program"]["global_energy_j"] for run in runs]
    sampled_whole_energies = [
        run["whole_program"]["sampled_energy_j"] for run in runs
    ]
    regional_statistics = {
        region_id: _series_statistics(
            [run["regions"][region_id]["energy_j"] for run in runs]
        )
        for region_id in REQUIRED_REGION_IDS
    }

    median_error = statistics.median(errors)
    accuracy_accepted = all(
        group["accuracy"]["accepted"] for group in configuration_groups
    )
    configuration_count_accepted = (
        required_configurations is None
        or len(configuration_groups) == required_configurations
    )
    variability_preferred = all(
        group["variability"]["preferred"] for group in configuration_groups
    )
    maximum_group_root_cv = max(
        group["variability"]["region_0_cv_percent"]
        for group in configuration_groups
    )
    return {
        "attempted_run_count": len(data),
        "run_count": len(runs),
        "invalid_run_count": len(invalid_runs),
        "invalid_runs": invalid_runs,
        "required_runs": required_runs,
        "configuration_count": len(configuration_groups),
        "required_configuration_count": required_configurations,
        "configuration_count_accepted": configuration_count_accepted,
        "configuration_groups": configuration_groups,
        "sensor_name": sensor_name,
        "global_domain": global_domain,
        "runs": runs,
        "accuracy": {
            "comparison": "sampled whole-program energy vs global RAPL energy",
            "median_absolute_error_percent": median_error,
            "mean_absolute_error_percent": statistics.fmean(errors),
            "maximum_absolute_error_percent": max(errors),
            "threshold_percent": max_median_error_percent,
            "accepted": configuration_count_accepted and accuracy_accepted,
        },
        "variability": {
            "primary_metric": "per-configuration region 0 sampled energy",
            "region_0_cv_percent": (
                maximum_group_root_cv
                if len(configuration_groups) == 1
                else None
            ),
            "maximum_group_region_0_cv_percent": maximum_group_root_cv,
            "preferred_threshold_percent": preferred_max_cv_percent,
            "preferred": variability_preferred,
        },
        "global_energy_statistics": _series_statistics(global_energies),
        "sampled_whole_energy_statistics": _series_statistics(
            sampled_whole_energies
        ),
        "regional_energy_statistics": regional_statistics,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Integrate sampled RAPL power for a five-run nested-region campaign "
            "and compare whole-program integration with global RAPL energy."
        )
    )
    parser.add_argument("json_path", type=Path)
    parser.add_argument("--sensor", default="rapl_sample-sysfs")
    parser.add_argument("--global-domain", default="rapl-sysfs")
    parser.add_argument("--require-runs", type=int, default=5)
    parser.add_argument("--max-median-error-percent", type=float, default=5.0)
    parser.add_argument("--preferred-max-cv-percent", type=float, default=10.0)
    parser.add_argument("--require-configurations", type=int)
    parser.add_argument(
        "--base-config",
        type=Path,
        help="base_config.json used to label Analyzer input indexes",
    )
    parser.add_argument("--output-json", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        with args.json_path.open("r", encoding="utf-8") as stream:
            document = json.load(stream)
        workloads = None
        base_config_path = args.base_config
        if base_config_path is None:
            candidate = args.json_path.parent / "base_config.json"
            if candidate.is_file():
                base_config_path = candidate
        if base_config_path is not None:
            with base_config_path.open("r", encoding="utf-8") as stream:
                base_config = json.load(stream)
            raw_workloads = base_config.get("workloads_list")
            if not isinstance(raw_workloads, list) or not all(
                isinstance(workload, str) for workload in raw_workloads
            ):
                raise EnergySummaryError(
                    "base config must contain a string workloads_list"
                )
            workloads = raw_workloads
        summary = summarize_document(
            document,
            sensor_name=args.sensor,
            global_domain=args.global_domain,
            required_runs=args.require_runs,
            max_median_error_percent=args.max_median_error_percent,
            preferred_max_cv_percent=args.preferred_max_cv_percent,
            workloads=workloads,
            required_configurations=args.require_configurations,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, EnergySummaryError) as exc:
        print(f"validation_error={exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False)
    print(rendered)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
        print(f"summary={args.output_json}")

    if any(
        group["run_count"] < args.require_runs
        for group in summary["configuration_groups"]
    ):
        return 3
    if not summary["configuration_count_accepted"]:
        return 3
    if not summary["accuracy"]["accepted"]:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
