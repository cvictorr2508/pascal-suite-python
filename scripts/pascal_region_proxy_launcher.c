#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include "pascalops.h"

#define MAX_LINE 512
#define MAX_FILENAME 256

static int write_ack(int fd, const char *message) {
    size_t length = strlen(message);
    ssize_t written = write(fd, message, length);
    if (written < 0 || (size_t)written != length) {
        perror("write ack");
        return -1;
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
        perror("fdopen command pipe");
        return 40;
    }

    char line[MAX_LINE];
    int region_open = 0;
    long open_region_id = -1;

    while (fgets(line, sizeof(line), commands) != NULL) {
        char command[16] = {0};
        char filename[MAX_FILENAME] = {0};
        long region_id = -1;
        int line_no = 0;

        if (!parse_command(line, command, &region_id, &line_no, filename)) {
            fprintf(stderr, "proxy: comando invalido: %s", line);
            write_ack(ack_fd, "ERR invalid-command\n");
            continue;
        }

        if (strcmp(command, "START") == 0) {
            if (region_open) {
                fprintf(stderr, "proxy: START recebido com regiao %ld ainda aberta\n", open_region_id);
                write_ack(ack_fd, "ERR region-already-open\n");
                continue;
            }

            _pascal_start(region_id, line_no, filename);
            region_open = 1;
            open_region_id = region_id;
            printf("PROXY START region=%ld line=%d file=%s\n", region_id, line_no, filename);
            fflush(stdout);
            if (write_ack(ack_fd, "OK START\n") != 0) {
                break;
            }
            continue;
        }

        if (strcmp(command, "STOP") == 0) {
            if (!region_open || open_region_id != region_id) {
                fprintf(stderr, "proxy: STOP inconsistente para regiao %ld\n", region_id);
                write_ack(ack_fd, "ERR region-not-open\n");
                continue;
            }

            _pascal_stop(region_id, line_no, filename);
            region_open = 0;
            open_region_id = -1;
            printf("PROXY STOP region=%ld line=%d file=%s\n", region_id, line_no, filename);
            fflush(stdout);
            if (write_ack(ack_fd, "OK STOP\n") != 0) {
                break;
            }
            continue;
        }

        fprintf(stderr, "proxy: comando desconhecido: %s\n", command);
        write_ack(ack_fd, "ERR unknown-command\n");
    }

    fclose(commands);
    close(ack_fd);

    int status = 0;
    if (waitpid(child_pid, &status, 0) < 0) {
        perror("waitpid");
        return 41;
    }

    if (region_open) {
        fprintf(stderr, "proxy: child encerrou com regiao %ld ainda aberta\n", open_region_id);
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

int main(void) {
    const char *python = getenv("PASCAL_PYTHON_BIN");
    const char *script = getenv("PASCAL_PROXY_SCRIPT");
    if (python == NULL || script == NULL) {
        fprintf(stderr, "PASCAL_PYTHON_BIN e PASCAL_PROXY_SCRIPT sao obrigatorios\n");
        return 20;
    }

    int command_pipe[2];
    int ack_pipe[2];
    if (pipe(command_pipe) != 0 || pipe(ack_pipe) != 0) {
        perror("pipe");
        return 21;
    }

    pid_t pid = fork();
    if (pid < 0) {
        perror("fork");
        return 22;
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

        execl(python, python, script, (char *)NULL);
        perror("execl python");
        _exit(23);
    }

    close(command_pipe[1]);
    close(ack_pipe[0]);

    printf("PASCAL_REGION_PROXY supervisor_pid=%ld child_pid=%ld\n", (long)getpid(), (long)pid);
    fflush(stdout);

    return supervise_child(command_pipe[0], ack_pipe[1], pid);
}
