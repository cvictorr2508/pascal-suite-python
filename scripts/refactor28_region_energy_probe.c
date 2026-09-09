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

int main(void) {
    const double target_seconds = 3.0;
    const double start = monotonic_seconds();
    volatile uint64_t accumulator = 0x123456789abcdef0ULL;

    if (start < 0.0) {
        perror("clock_gettime");
        return 2;
    }

    pascal_start(1);
    while (monotonic_seconds() - start < target_seconds) {
        accumulator ^= accumulator << 7;
        accumulator ^= accumulator >> 9;
        accumulator *= 0x9e3779b97f4a7c15ULL;
    }
    pascal_stop(1);

    printf("refactor28_probe accumulator=%llu\n", (unsigned long long)accumulator);
    return 0;
}
