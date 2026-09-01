#define _POSIX_C_SOURCE 200809L

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#include "pascalops.h"

static double monotonic_seconds(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
        perror("clock_gettime");
        exit(10);
    }
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1.0e9;
}

static int native_selftest(void) {
    volatile uint64_t value = 1;
    const double deadline = monotonic_seconds() + 2.0;

    puts("ANTES DA REGIAO NATIVA LAUNCHER");
    fflush(stdout);

    pascal_start(9);
    while (monotonic_seconds() < deadline) {
        value = value * 1664525u + 1013904223u;
    }
    pascal_stop(9);

    puts("DEPOIS DA REGIAO NATIVA LAUNCHER");
    printf("value=%llu\n", (unsigned long long)value);
    fflush(stdout);
    return 0;
}

static void exec_python(void) {
    const char *python = getenv("PASCAL_PYTHON_BIN");
    const char *script = getenv("PASCAL_DIAG_SCRIPT");

    if (python == NULL || script == NULL) {
        fprintf(stderr, "PASCAL_PYTHON_BIN e PASCAL_DIAG_SCRIPT sao obrigatorios\n");
        exit(20);
    }

    setenv("PASCAL_LOADER_MODE", "baseline", 1);
    execl(python, python, script, (char *)NULL);
    perror("execl python");
    exit(21);
}

static int spawn_python(void) {
    pid_t pid = fork();
    if (pid < 0) {
        perror("fork");
        return 30;
    }

    if (pid == 0) {
        exec_python();
    }

    int status = 0;
    if (waitpid(pid, &status, 0) < 0) {
        perror("waitpid");
        return 31;
    }

    if (WIFEXITED(status)) {
        return WEXITSTATUS(status);
    }
    if (WIFSIGNALED(status)) {
        fprintf(stderr, "python child terminou por sinal %d\n", WTERMSIG(status));
        return 128 + WTERMSIG(status);
    }
    return 32;
}

int main(void) {
    const char *mode = getenv("PASCAL_LAUNCHER_MODE");
    if (mode == NULL) {
        mode = "selftest";
    }

    printf("PASCAL_LAUNCHER_MODE=%s pid=%ld\n", mode, (long)getpid());
    fflush(stdout);

    if (strcmp(mode, "selftest") == 0) {
        return native_selftest();
    }
    if (strcmp(mode, "exec") == 0) {
        exec_python();
    }
    if (strcmp(mode, "spawn") == 0) {
        return spawn_python();
    }

    fprintf(stderr, "modo desconhecido: %s\n", mode);
    return 2;
}
