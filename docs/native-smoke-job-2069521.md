# Native smoke job 2069521

The first native C smoke job did not reach PaScal execution. GCC 8.5.0 failed during compilation because `CLOCK_MONOTONIC` and `clock_gettime` were not exposed under `-std=c11` without a POSIX feature-test macro.

Observed compiler diagnostics:

- implicit declaration of `clock_gettime`;
- `CLOCK_MONOTONIC` undeclared.

This result is a build-toolchain failure only and does not provide evidence for or against PaScal manual-region registration.

The source was corrected by defining `_POSIX_C_SOURCE 200809L` before system headers. A standalone build-check script was also added so the next SLURM job is submitted only after the native smoke executable builds successfully.
