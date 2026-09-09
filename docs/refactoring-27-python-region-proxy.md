# Refactoring 27 — PaScal regions for Python workloads

## Objective

Resolve Issue #3 by recording PaScal manual regions during Python/Gurobi
workloads without fabricating or post-processing Analyzer telemetry.
`region_energy` remained outside this refactoring and under Issue #4.

## Diagnosis

Refactoring 26 corrected the `_pascal_start/_pascal_stop` `ctypes` ABI and
eliminated the segmentation fault, but the Python process still did not produce
`data[*].regions["1"]`.

1. NPAD job `2069965` tested baseline, `LD_PRELOAD`, and `RTLD_GLOBAL`. None
   crashed and none recorded region `1`; library loading time/scope was not the
   cause.
2. Job `2070698` showed that a linked native self-test recorded an approximately
   two-second region, while `exec()` and `fork()+exec()` paths into Python did
   not. The instrumentation calls had to run in the native process recognized
   by the Analyzer.
3. Job `2070730` launched a native ELF supervisor directly under the Analyzer.
   Python sent `START/STOP` messages over pipes and waited for acknowledgements.
   Region `1` appeared in the native JSON, with `2.000082016 s` measured for an
   approximately two-second Python window. Fourteen tests passed at that stage.

## Production architecture

```text
pascalanalyzer
    |
    v
ELF supervisor linked with libmpascalops
    |
    +-- starts the solver runner
    +-- receives START/STOP over pipes
    +-- executes _pascal_start/_pascal_stop in the native process
```

Python keeps the context-manager API:

```python
with pascal_region(1):
    model.optimize()
```

When proxy descriptors are available, `pascal_region()` uses IPC and Python
does not load `libmpascalops.so`. The lazy `ctypes` fallback is reserved for use
outside the proxy.

## Permanent components

- `src/pascalpy/instrumentation/native/pascal_region_proxy.c`: native
  supervisor.
- `src/pascalpy/instrumentation/proxy_builder.py`: deterministic compilation and
  linking in the output directory.
- `src/pascalpy/instrumentation/pascalops.py`: proxy/ctypes selection and the
  START/STOP protocol.
- `src/pascalpy/adapters/gurobi_adapter.py`: makes the Analyzer launch the ELF
  supervisor directly.
- `src/pascalpy/runners/gurobi_runner.py`: surrounds `model.optimize()` with the
  solver region and records the backend in metadata.

## Gurobi validation

### One-core smoke — job 2070776

The complete `rodar_yaml.py -> GurobiFileAdapter -> pascalanalyzer -> supervisor
-> gurobi_runner.py` path completed with status `0:0`. The validator observed a
proxy backend, matching requested/effective thread count, region `1`, PaScal
duration `0.060197830 s`, Gurobi runtime `0.059804916 s`, solve wall time
`0.060487831 s`, and `proxy_smoke_valid=true`.

### Lazy loading

The fallback became lazy to avoid a spurious `Pascal not running` message during
import and test discovery. The regression verifies that importing `pascalops`
in a clean subprocess does not touch the native runtime. The final suite passed
without that message or `Bad file descriptor`.

### Structural strong scaling

The final gate used `dummy.mps`, resources `[1, 2, 4]`, and one repetition. For
every configuration it confirmed the region, proxy backend, matching requested
and effective thread counts, affinity cardinality, Gurobi metrics, and timing
agreement. Monotonic speedup was not required because the dummy model is a
structural fixture rather than a performance benchmark.

## Acceptance criteria

- [x] Python workload produces a manual region.
- [x] Region timing agrees with the measured window.
- [x] No `SIGSEGV/-11`.
- [x] No PaScal JSON post-processing.
- [x] `model.optimize()` remains the solver region.
- [x] Structural scaling preserves `cores == Threads`.
- [x] Package import does not probe the native runtime unexpectedly.

The lack of Analyzer-provided `region_energy` remained a separate known limit.

