# Refactoring 28 — Track A: Viewer-derived regional energy

## Architectural decision

`pascal-suite-python` neither fabricates `region_energy` domains nor restructures
Analyzer JSON. When RAPL is enabled, the adapter requests both native products:

```text
--rple BACKEND --rpls BACKEND
```

`--rple` provides independent global energy for validation. `--rpls` provides
the `[power, timestamp]` series that the Viewer integrates over intervals in
`regions`.

## Contract states

The diagnostic distinguishes three capabilities:

1. `legacy_region_energy_ready`: a historical descriptor containing
   `values: ["region_energy"]` and a numeric region map;
2. `viewer_energy_ready`: an `extras` entry beginning with `rapl` and containing
   a numeric region map, matching the earlier Viewer contract;
3. `sampled_energy_derivable`: a region and at least two ordered
   `rapl_sample-*` observations covering its intervals.

The third state confirms sufficient input data; it does not itself prove that a
deployed Viewer version will display regional energy.

## Viewer algorithm

For each execution and `rapl_sample-*` sensor, the Viewer must:

1. require finite values and strictly increasing timestamps;
2. sort and merge every occurrence of the same region ID;
3. clip intervals to execution bounds;
4. interpolate power at interval boundaries and integrate trapezoidally;
5. extend the first or last sample by at most one sampling period;
6. use the union of overlapping thread intervals to avoid double-counting
   package energy;
7. use `--rple` only as an independent consistency control.

The derived domain may retain the backend identity, such as `rapl-sysfs`, in
the Viewer model. The uploaded file remains unchanged.

## Acceptance criteria

- A validation workload lasting at least five seconds.
- Five repetitions with positive regional energy.
- A control region covering nearly the complete execution.
- Median relative error no greater than 5% against `--rple`.
- A separate repeated/overlapping-region test using interval union.
- Energy and EDP displayed directly from native JSON.
- No JSON transformation in the Python wrapper.

The initial three-second probe obtained 0.269% error and supported the approach.

## NPAD calibration gate

Job `2079023` ran five one-core repetitions of
`CFL_hard_instance_20.lp.gz`. Median absolute error was 0.196%, maximum error
0.333%, and energy CV was 1.688% for region `0`, 1.269% for `0.1`, and 6.412%
for `0.2`. All repetitions produced positive energy. Four root regions covered
about 99% of execution; the first covered 85.534% because of initialization.
Both the mandatory 5% error gate and preferred 10% CV gate passed.

## Representative campaign design

The first 75-attempt campaign exposed an isolated invalid `sysfs` observation:
run `4;1;4` had global energy `-261400.335 J` and sampled power
`-2621371.789 W`, while the four peer runs reported 728.700–765.659 J. The
negative values were physically invalid and could not be integrated or imputed.

The representative gate therefore used hard instances 5, 10, 15, 20, and 25,
resources `[1, 2, 4]`, and six attempts, for 90 total runs. It recorded invalid
attempts, required five valid runs in each of 15 configurations, and calculated
error and CV per instance/resource group.

## Initial accepted campaign — job 2080062

Job `2080062` completed with status `0:0`. Of 90 attempts, 89 were accepted.
Run `4;3;3` was rejected for non-positive global energy and negative power; it
was not corrected or imputed. Its configuration retained five valid runs.

- 15/15 configurations accepted.
- Median absolute error: 0.207439%.
- Mean absolute error: 0.206935%.
- Maximum absolute error: 0.479272%.
- Maximum configuration-level region-0 CV: 2.160181%.
- Root coverage: 85.497455% to 99.092470%.
- Maximum root/child duration difference: 0.000598 s.

Evidence was retained externally under
`pascal-suite-python-evidence/refactor28/job-2080062`, with recorded SHA-256
hashes for stdout, stderr, summary, and the campaign archive. This gate
established the component-level TRL 5 MVP. End-to-end Viewer integration was the
remaining step toward the bounded TRL 6 demonstration and was subsequently
validated in the separate Viewer repository.

