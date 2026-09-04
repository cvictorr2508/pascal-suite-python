#define _POSIX_C_SOURCE 200809L

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include "pascalops.h"

#define MAX_LINE 512
#define MAX_FILENAME 256
#define MAX_OPEN_REGIONS 64

static int write_all(int fd, const char *message) {
    size_t remaining = strlen(message);
    const char *cursor = message;

    while (remaining > 0) {
        ssize_t written = write(fd, cursor, remaining);
        if (written <= 0) {
            perror("proxy write");
            return -1;
        }
        cursor += written;
        remaining -= (size_t)written;
    }
    return 0;
}

static int parse_command(
    const char *line,
    char *command,
    long *region_id,
    int *line_no,
    char *filename
) {
    return sscanf(
        line,
        "%15s\t%ld\t%d\t%255[^\n]",
        command,
        region_id,
        line_no,
        filename
    ) == 4;
}

static int supervise_child(int command_fd, int ack_fd, pid_t child_pid) {
    FILE *commands = fdopen(command_fd, "r");
    if (commands == NULL) {
        perror("proxy fdopen");
        return 40;
    }

    char line[MAX_LINE];
    long open_region_ids[MAX_OPEN_REGIONS] = {0};
    size_t open_region_count = 0;

    while (fgets(line, sizeof(line), commands) != NULL) {
        char command[16] = {0};
        char filename[MAX_FILENAME] = {0};
        long region_id = -1;
        int line_no = 0;

        if (!parse_command(line, command, &region_id, &line_no, filename)) {
            fprintf(stderr, "proxy: comando inválido: %s", line);
            write_all(ack_fd, "ERR invalid-command\n");
            continue;
        }

        if (strcmp(command, "START") == 0) {
            if (open_region_count >= MAX_OPEN_REGIONS) {
                fprintf(stderr, "proxy: limite de regiões aninhadas excedido\n");
                write_all(ack_fd, "ERR region-stack-full\n");
                continue;
            }

            _pascal_start(region_id, line_no, filename);
            open_region_ids[open_region_count] = region_id;
            open_region_count += 1;
            printf(
                "PASCAL_PROXY START region=%ld depth=%zu line=%d file=%s\n",
                region_id,
                open_region_count,
                line_no,
                filename
            );
            fflush(stdout);
            if (write_all(ack_fd, "OK START\n") != 0) {
                break;
            }
            continue;
        }

        if (strcmp(command, "STOP") == 0) {
            if (
                open_region_count == 0
                || open_region_ids[open_region_count - 1] != region_id
            ) {
                fprintf(
                    stderr,
                    "proxy: STOP inconsistente para região %ld\n",
                    region_id
                );
                write_all(ack_fd, "ERR region-not-open\n");
                continue;
            }

            _pascal_stop(region_id, line_no, filename);
            open_region_count -= 1;
            printf(
                "PASCAL_PROXY STOP region=%ld depth=%zu line=%d file=%s\n",
                region_id,
                open_region_count,
                line_no,
                filename
            );
            fflush(stdout);
            if (write_all(ack_fd, "OK STOP\n") != 0) {
                break;
            }
            continue;
        }

        fprintf(stderr, "proxy: comando desconhecido: %s\n", command);
        write_all(ack_fd, "ERR unknown-command\n");
    }

    fclose(commands);
    close(ack_fd);

    int status = 0;
    if (waitpid(child_pid, &status, 0) < 0) {
        perror("proxy waitpid");
        return 41;
    }

    if (open_region_count > 0) {
        fprintf(
            stderr,
            "proxy: child terminou com %zu região(ões) ainda aberta(s); topo=%ld\n",
            open_region_count,
            open_region_ids[open_region_count - 1]
        );
        return 42;
    }

    if (WIFEXITED(status)) {
        return WEXITSTATUS(status);
    }
    if (WIFSIGNALED(status)) {
        fprintf(stderr, "proxy: child terminou por sinal %d\n", WTERMSIG(status));
        return 128 + WTERMSIG(status);
    }
    return 43;
}

int main(int argc, char **argv) {
    const char *python = getenv("PASCAL_PROXY_PYTHON_BIN");
    const char *runner = getenv("PASCAL_PROXY_RUNNER");
    const char *base_config = getenv("PASCAL_PROXY_BASE_CONFIG");

    if (argc < 2) {
        fprintf(stderr, "proxy: workload não foi fornecido pelo pascalanalyzer -i\n");
        return 20;
    }
    if (python == NULL || runner == NULL || base_config == NULL) {
        fprintf(
            stderr,
            "proxy: PASCAL_PROXY_PYTHON_BIN, PASCAL_PROXY_RUNNER e PASCAL_PROXY_BASE_CONFIG são obrigatórios\n"
        );
        return 21;
    }

    const char *workload = argv[1];
    int command_pipe[2];
    int ack_pipe[2];

    if (pipe(command_pipe) != 0 || pipe(ack_pipe) != 0) {
        perror("proxy pipe");
        return 22;
    }

    pid_t pid = fork();
    if (pid < 0) {
        perror("proxy fork");
        return 23;
    }

    if (pid == 0) {
        close(command_pipe[0]);
        close(ack_pipe[1]);

        char command_fd[32];
        char ack_fd[32];
        snprintf(command_fd, sizeof(command_fd), "%d", command_pipe[1]);
        snprintf(ack_fd, sizeof(ack_fd), "%d", ack_pipe[0]);

        setenv("PASCAL_REGION_PROXY_COMMAND_FD", command_fd, 1);
        setenv("PASCAL_REGION_PROXY_ACK_FD", ack_fd, 1);
        setenv("PASCAL_REGION_PROXY_ACTIVE", "1", 1);

        execl(
            python,
            python,
            runner,
            "--base-config",
            base_config,
            "--workload",
            workload,
            (char *)NULL
        );
        perror("proxy execl python");
        _exit(24);
    }

    close(command_pipe[1]);
    close(ack_pipe[0]);

    printf(
        "PASCAL_REGION_PROXY supervisor_pid=%ld child_pid=%ld workload=%s\n",
        (long)getpid(),
        (long)pid,
        workload
    );
    fflush(stdout);

    return supervise_child(command_pipe[0], ack_pipe[1], pid);
}
