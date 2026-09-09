#!/usr/bin/env python3

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pascalpy.validation.pascal_energy import validate_pascal_energy_document  # noqa: E402


def summarize(path: Path) -> dict:
    if not path.is_file():
        return {"exists": False, "file": str(path)}

    payload = json.loads(path.read_text(encoding="utf-8"))
    descriptor = ((payload.get("config") or {}).get("data_descriptor") or {})
    extras = descriptor.get("extras") or {}
    data = payload.get("data") or {}

    report = validate_pascal_energy_document(
        payload,
        source=str(path),
        required_region_id=1,
    )

    run_summaries = {}
    for run_key, run in data.items():
        if not isinstance(run, dict):
            continue
        sensors = run.get("sensors")
        sensor_names = sorted(sensors) if isinstance(sensors, dict) else []
        global_rapl = sorted(
            key
            for key, value in run.items()
            if str(key).startswith("rapl") and not isinstance(value, dict)
        )
        run_summaries[str(run_key)] = {
            "has_region_1": bool(
                isinstance(run.get("regions"), dict)
                and (run.get("regions") or {}).get("1")
            ),
            "global_rapl_keys": global_rapl,
            "sensor_names": sensor_names,
            "region_energy_domains_present": sorted(
                domain
                for domain in report.rapl_domains
                if isinstance(run.get(domain), dict)
            ),
        }

    return {
        "exists": True,
        "file": str(path),
        "descriptor_values": descriptor.get("values") or [],
        "extras": {
            str(name): (entry.get("values") if isinstance(entry, dict) else None)
            for name, entry in extras.items()
        },
        "runs": run_summaries,
        "energy_validation": report.to_dict(),
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: summarize_refactor28_region_energy.py JSON...", file=sys.stderr)
        return 2

    summaries = {}
    ready_modes = []
    derivable_modes = []
    for raw_path in sys.argv[1:]:
        path = Path(raw_path)
        mode = path.stem.removeprefix("refactor28_energy_")
        summary = summarize(path)
        summaries[mode] = summary
        if (summary.get("energy_validation") or {}).get("viewer_energy_ready") is True:
            ready_modes.append(mode)
        if (summary.get("energy_validation") or {}).get(
            "sampled_energy_derivable"
        ) is True:
            derivable_modes.append(mode)

    print(json.dumps(summaries, indent=2, sort_keys=True, ensure_ascii=False))
    print("viewer_energy_ready_modes=" + ",".join(sorted(ready_modes)))
    print("sampled_energy_derivable_modes=" + ",".join(sorted(derivable_modes)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
