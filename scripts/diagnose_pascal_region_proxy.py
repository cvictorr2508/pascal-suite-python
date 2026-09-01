#!/usr/bin/env python3

import json
import os
import time
from pathlib import Path


def _fd_from_env(name: str) -> int:
    raw = os.environ.get(name)
    if raw is None:
        raise RuntimeError(f"{name} ausente")
    return int(raw)


def _send_and_wait(command_fd: int, ack_fd: int, message: str) -> str:
    os.write(command_fd, message.encode("utf-8"))
    chunks = []
    while True:
        chunk = os.read(ack_fd, 1)
        if not chunk:
            raise RuntimeError("proxy encerrou o canal de ACK")
        chunks.append(chunk)
        if chunk == b"\n":
            break
    reply = b"".join(chunks).decode("utf-8").strip()
    if not reply.startswith("OK "):
        raise RuntimeError(f"proxy rejeitou comando: {reply}")
    return reply


def main() -> int:
    command_fd = _fd_from_env("PASCAL_REGION_PROXY_COMMAND_FD")
    ack_fd = _fd_from_env("PASCAL_REGION_PROXY_ACK_FD")
    filename = Path(__file__).name

    print(
        json.dumps(
            {
                "pid": os.getpid(),
                "command_fd": command_fd,
                "ack_fd": ack_fd,
                "filename": filename,
            },
            sort_keys=True,
        ),
        flush=True,
    )

    print("ANTES DA REGIAO PYTHON VIA PROXY", flush=True)
    start_reply = _send_and_wait(
        command_fd,
        ack_fd,
        f"START\t1\t100\t{filename}\n",
    )
    started = time.perf_counter()

    deadline = started + 2.0
    value = 1
    while time.perf_counter() < deadline:
        value = (value * 1664525 + 1013904223) & 0xFFFFFFFF

    stopped = time.perf_counter()
    stop_reply = _send_and_wait(
        command_fd,
        ack_fd,
        f"STOP\t1\t110\t{filename}\n",
    )

    print("DEPOIS DA REGIAO PYTHON VIA PROXY", flush=True)
    print(
        json.dumps(
            {
                "start_reply": start_reply,
                "stop_reply": stop_reply,
                "elapsed_region_wall_s": stopped - started,
                "value": value,
            },
            sort_keys=True,
        ),
        flush=True,
    )

    os.close(command_fd)
    os.close(ack_fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
