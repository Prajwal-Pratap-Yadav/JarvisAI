"""Bounded subprocesses with cancellation cleanup. Never invoke a command shell."""

from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path
from typing import Any


async def run_process(argv: list[str], cwd: Path, timeout: float = 30) -> dict:  # noqa: ASYNC109 — cleanup owns the deadline
    # Do not pass provider or access credentials into project tests or child programs.
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "LANG", "LOCALAPPDATA"}
    env = {key: value for key, value in os.environ.items() if key in allowed}
    env["PYTHONIOENCODING"] = "utf-8"
    kwargs: dict[str, Any] = (
        {"start_new_session": True} if os.name != "nt" else {"creationflags": 0x00000200}
    )
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        **kwargs,
    )
    captured = bytearray()

    async def read() -> None:
        assert process.stdout is not None
        while chunk := await process.stdout.read(4096):
            if len(captured) < 60000:
                captured.extend(chunk[: 60000 - len(captured)])

    reader = asyncio.create_task(read())
    try:
        await asyncio.wait_for(process.wait(), timeout)
        await asyncio.wait_for(reader, 2)
    finally:
        # Also terminate grandchildren that outlive their original test process.
        if os.name == "nt":
            if process.returncode is None:
                import psutil

                try:
                    parent = psutil.Process(process.pid)
                    for child in parent.children(recursive=True):
                        child.kill()
                    parent.kill()
                except psutil.NoSuchProcess:
                    pass
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.returncode is None:
            await process.wait()
        reader.cancel()
        await asyncio.gather(reader, return_exceptions=True)
    return {
        "exit_code": process.returncode,
        "output": captured.decode("utf-8", errors="replace"),
        "truncated": len(captured) == 60000,
    }
