#define _POSIX_C_SOURCE 200809L

#include <stdint.h>
#include <stdio.h>
#include <time.h>

#include "pascalops.h"

static double monotonic_seconds(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1.0e9;
}

int main(void) {
    volatile uint64_t value = 1;
    const double deadline = monotonic_seconds() + 2.0;

    puts("ANTES DA REGIAO NATIVA");
    fflush(stdout);

    pascal_start(1);
    while (monotonic_seconds() < deadline) {
        value = value * 1664525u + 1013904223u;
    }
    pascal_stop(1);

    puts("DEPOIS DA REGIAO NATIVA");
    printf("value=%llu\n", (unsigned long long)value);
    fflush(stdout);

    return 0;
}
