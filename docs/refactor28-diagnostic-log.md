# Refactoring 28 — diagnostic log

## Current state

### Job 2071093 — RAPL backend matrix

- `--rple sysfs`: manual region and global energy present; no `region_energy`.
- `--rpls sysfs`: manual region and RAPL samples present; no `region_energy`.
- Every case containing `perf` aborted before writing JSON with
  `ModuleNotFoundError: No module named 'profiler'`.
- The Analyzer returned status 0 even for those aborts, so success also requires
  a valid JSON artifact.

### Job 2071932 — perf runtime

- `perf_event_paranoid=-1`.
- `power/energy-pkg/` and `power/energy-ram/` were available.
- `perf stat` measured RAPL successfully.
- `python_profiler_available=false`.
- The Analyzer contained PyInstaller bundle signatures.

Conclusion: the `perf` backend was blocked by the Analyzer runtime/package, not
by NPAD hardware, kernel settings, or user permissions.

### Official release

The `pascalanalyzer` binary from `lappsufrn/pascal-releases/master` was
byte-for-byte identical to the NPAD `2025-07-08` snapshot, including SHA-256 and
BuildID. Reinstalling that release would not change the observed behavior.

### PyInstaller inspection

The first attempt to install `pyinstaller>=6,<7` failed because the default NPAD
package index exposed versions only through 4.10. Python 3.13 support started in
PyInstaller 6.10, so the isolated diagnostic probe was changed to require
`pyinstaller>=6.10,<7` and explicitly fall back to `https://pypi.org/simple`.

Inspection of the embedded archive and four historical binaries materialized
from Git LFS found no implementation of the regional-energy contract.

### Regional aggregation with `-a 1`

The gate exercised `--rpls sysfs`, `--rple sysfs`, both flags, and `--ragt acc`.
Every case produced valid JSON, but none declared or wrote a per-region RAPL map.
Aggregation added only `imbalances` and `measurements`; it does not enable
regional energy and is not part of the production path.

### Quantitative sampled-RAPL evidence

In the approximately three-second probe, `--rple sysfs --rpls sysfs` produced:

- global energy: `150.727032 J`;
- mean sampled power: `50.377923 W`;
- trapezoidal region-1 estimate: `151.133062 J`;
- relative difference from global energy: `0.269%`.

The native samples are sufficient to derive regional energy without rewriting
the JSON. PaScal Analyzer remains the telemetry authority; the Viewer integrates
the sampled series. The adapter requests `--rple` as an independent global
control and `--rpls` as the power series.

The historical `testeIM.json` remains useful as a format reference, but not as a
numeric oracle: for repeated regions, its saved value is consistent with the
last occurrence rather than the sum or temporal union of all occurrences.

