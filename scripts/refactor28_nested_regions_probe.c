#define _POSIX_C_SOURCE 200809L

#include <stdint.h>
#include <stdio.h>
#include <time.h>

#include "pascalops.h"

static double monotonic_seconds(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
        return -1.0;
    }
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1.0e9;
}

static int burn_for(double seconds, volatile uint64_t *accumulator) {
    const double start = monotonic_seconds();
    if (start < 0.0) {
        return -1;
    }

    while (monotonic_seconds() - start < seconds) {
        *accumulator ^= *accumulator << 7;
        *accumulator ^= *accumulator >> 9;
        *accumulator *= 0x9e3779b97f4a7c15ULL;
    }
    return 0;
}

int main(void) {
    volatile uint64_t accumulator = 0x123456789abcdef0ULL;
    int build_rc;
    int solve_rc;

    pascal_start(0);

    pascal_start(1);
    build_rc = burn_for(5.0, &accumulator);
    pascal_stop(1);

    pascal_start(2);
    solve_rc = burn_for(3.0, &accumulator);
    pascal_stop(2);

    pascal_stop(0);

    if (build_rc != 0 || solve_rc != 0) {
        perror("clock_gettime");
        return 2;
    }

    printf(
        "nested_regions_probe accumulator=%llu\n",
        (unsigned long long)accumulator
    );
    return 0;
}
