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
) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise EnergySummaryError("JSON root must be an object")
    data = document.get("data")
    if not isinstance(data, dict) or not data:
        raise EnergySummaryError("JSON must contain non-empty data")

    runs: list[dict[str, Any]] = []
    for run_key in sorted(data):
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
    root_cv = regional_statistics["0"]["cv_percent"]
    run_count_accepted = len(runs) >= required_runs
    return {
        "run_count": len(runs),
        "required_runs": required_runs,
        "sensor_name": sensor_name,
        "global_domain": global_domain,
        "runs": runs,
        "accuracy": {
            "comparison": "sampled whole-program energy vs global RAPL energy",
            "median_absolute_error_percent": median_error,
            "mean_absolute_error_percent": statistics.fmean(errors),
            "maximum_absolute_error_percent": max(errors),
            "threshold_percent": max_median_error_percent,
            "accepted": run_count_accepted
            and median_error <= max_median_error_percent,
        },
        "variability": {
            "primary_metric": "region 0 sampled energy",
            "region_0_cv_percent": root_cv,
            "preferred_threshold_percent": preferred_max_cv_percent,
            "preferred": run_count_accepted
            and root_cv <= preferred_max_cv_percent,
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
    parser.add_argument("--output-json", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        with args.json_path.open("r", encoding="utf-8") as stream:
            document = json.load(stream)
        summary = summarize_document(
            document,
            sensor_name=args.sensor,
            global_domain=args.global_domain,
            required_runs=args.require_runs,
            max_median_error_percent=args.max_median_error_percent,
            preferred_max_cv_percent=args.preferred_max_cv_percent,
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

    if summary["run_count"] < args.require_runs:
        return 3
    if not summary["accuracy"]["accepted"]:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

