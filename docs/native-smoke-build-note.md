# Native PaScal smoke build note

The first native smoke submission (`2069521`) failed during C compilation before the PaScal Analyzer was executed. With GCC 8.5.0 and `-std=c11`, `clock_gettime`/`CLOCK_MONOTONIC` were hidden because the required POSIX feature-test macro was not defined.

The smoke source now defines `_POSIX_C_SOURCE 200809L` before including system headers. No PaScal logic or instrumentation semantics were changed.

The native smoke remains a diagnostic gate:

- if native C regions appear in the Analyzer JSON, investigate Python/ctypes integration;
- if native C regions also do not appear, investigate the NPAD PaScal manual-instrumentation runtime/configuration before changing the Python wrapper again.
