"""Start the shared GRU shell and its isolated role runtimes."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
WORKERS = (
    (
        "Bob",
        ROOT,
        8091,
        "ui.app:app",
        (ROOT / "project-gru-revops-poc-main", ROOT),
    ),
    (
        "James",
        ROOT / "GRU-Marketing",
        8092,
        "ui.app:app",
        (ROOT / "GRU-Marketing", ROOT / "GRU-Marketing" / "packages"),
    ),
    (
        "Stuart",
        ROOT,
        8093,
        "ui.stuart_app:app",
        (ROOT / "stuart-sales-manager-assistant", ROOT),
    ),
    (
        "Henry",
        ROOT,
        8094,
        "ui.henry_app:app",
        (ROOT / "GRU_DSR", ROOT),
    ),
)


def _worker_env(paths: tuple[Path, ...]) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    values = [str(path) for path in paths]
    if existing:
        values.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(values)
    return env


def _start_workers() -> list[subprocess.Popen]:
    processes: list[subprocess.Popen] = []
    for name, cwd, port, target, paths in WORKERS:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                target,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=cwd,
            env=_worker_env(paths),
        )
        process.gru_name = name  # type: ignore[attr-defined]
        processes.append(process)
    return processes


def _wait_for_workers(processes: list[subprocess.Popen]) -> None:
    deadline = time.monotonic() + 60
    pending = {8091: "Bob", 8092: "James", 8093: "Stuart", 8094: "Henry"}
    while pending and time.monotonic() < deadline:
        for process in processes:
            if process.poll() is not None:
                name = getattr(process, "gru_name", "Role runtime")
                raise RuntimeError(f"{name} failed to start (exit {process.returncode}).")
        for port in list(pending):
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/workspace", timeout=1
                ) as response:
                    if response.status == 200:
                        pending.pop(port)
            except (urllib.error.URLError, TimeoutError):
                pass
        if pending:
            time.sleep(0.2)
    if pending:
        names = ", ".join(pending.values())
        raise RuntimeError(f"Timed out waiting for: {names}")


def _stop_workers(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + 5
    for process in processes:
        remaining = max(0, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> None:
    load_dotenv(ROOT / ".env")
    processes = _start_workers()
    try:
        _wait_for_workers(processes)
        uvicorn.run("ui.gateway:app", host="127.0.0.1", port=8080)
    finally:
        _stop_workers(processes)


if __name__ == "__main__":
    main()
