# Refactoring 26 — NPAD validation result

## Objective

Validate the PaScal manual instrumentation used by the Gurobi runner, correct
the Python binding, and determine whether the PaScal Analyzer installed at NPAD
produces the regional-energy contract expected by PaScal Viewer.

The validation used Python `3.13.7`, PaScal Suite `2025-07-08`, and
`libmpascalops.so` from the institutional PaScal installation.

## Manual-instrumentation ABI

The installed header declares:

```c
void _pascal_start(long id, int start_line, const char *filename);
void _pascal_stop(long id, int stop_line, const char *filename);
```

The previous binding passed only `region_id`, causing `SIGSEGV (-11)`. The
correct `ctypes` signature is:

```python
[ctypes.c_long, ctypes.c_int, ctypes.c_char_p]
```

for both start and stop. Refactoring 26 also resolves the available symbols
explicitly and records the diagnostic in runner metadata.

## Unit validation

The symbol probe and unit suite confirmed that `_pascal_start` and
`_pascal_stop` were available and that the corrected ABI no longer crashed.
Six tests passed at that stage.

## Python smoke result

After the ABI correction, Python no longer raised `SIGSEGV`, but its manual
region did not appear in the Analyzer JSON. This behavior was separated into
Issue #3: correctly record PaScal regions from Python workloads.

## Native C control

A native executable calling `pascal_start(1)` and `pascal_stop(1)` under
`pascalanalyzer -t man` recorded region `1` correctly, including timestamps,
source lines, thread ID, filename, and an approximately two-second duration.
This demonstrated that native manual instrumentation worked in the installed
build.

## RAPL mode matrix

Job `2069555` ran the same native program in three modes on one NPAD node.

### `--rple sysfs`

The descriptor contained start time, stop time, global `rapl-sysfs`, and
regions. Region `1` and global energy were present; `region_energy` was absent.

### `--rpls sysfs`

The descriptor contained start time, stop time, regions, and sensors. Region
`1` and timestamped `rapl_sample-sysfs` data were present; `region_energy` was
absent.

### `--rple sysfs --rpls sysfs`

Global energy, regions, and sampled RAPL power were all present;
`region_energy` remained absent. The job completed with status `0:0`.

## Regional-energy conclusion

No tested combination of `--rple` and `--rpls` in PaScal Suite `2025-07-08`
produced a `region_energy` descriptor or payload. A recursive search of the
installed tree also found no corresponding implementation. The regional-energy
contract seen in Viewer reference JSON was therefore not emitted by the NPAD
Analyzer build. Issue #4 tracked this separately.

## Approved scope

Refactoring 26 was accepted for:

1. correcting the `ctypes` ABI and eliminating its segmentation fault;
2. resolving and recording the symbols actually loaded;
3. failing fast when `libmpascalops` is unavailable;
4. recording instrumentation diagnostics in Gurobi metadata;
5. retaining an explicit regional-energy contract validator for future builds;
6. documenting the limitation of the NPAD `2025-07-08` build.

It deliberately did not claim to solve native region registration from a Python
process or to generate `region_energy`. It also did not fabricate or restructure
PaScal JSON.

## Final acceptance

- [x] Native symbols confirmed at NPAD.
- [x] Correct ABI implemented.
- [x] ABI-related `SIGSEGV (-11)` eliminated.
- [x] Six unit tests passed at that stage.
- [x] Native C manual instrumentation confirmed.
- [x] `--rple`, `--rpls`, and their combination characterized.
- [x] Absence of `region_energy` in the installed build demonstrated.
- [x] Remaining limitations separated into dedicated issues.

