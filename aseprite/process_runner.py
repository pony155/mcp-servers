"""Bounded, cancellable Aseprite child-process execution."""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .errors import AsepriteMCPError


@dataclass(frozen=True, slots=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


class ProcessRunner:
    def __init__(self, timeout_seconds: float, max_capture_bytes: int) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_capture_bytes = max_capture_bytes

    async def run(self, executable: Path, arguments: list[str]) -> ProcessResult:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = await asyncio.create_subprocess_exec(
            str(executable),
            *arguments,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=creationflags,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            await self._stop(process)
            raise AsepriteMCPError(
                "OPERATION_TIMEOUT",
                f"Aseprite exceeded the {self.timeout_seconds:g}-second timeout",
            ) from exc
        except asyncio.CancelledError:
            await self._stop(process)
            raise

        captured_size = len(stdout_bytes) + len(stderr_bytes)
        if captured_size > self.max_capture_bytes:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED", "Aseprite produced more diagnostic output than allowed"
            )

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        if process.returncode != 0:
            diagnostic = (stderr or stdout).strip()
            if len(diagnostic) > 2000:
                diagnostic = diagnostic[:2000] + "..."
            message = f"Aseprite exited with code {process.returncode}"
            if diagnostic:
                message += f": {diagnostic}"
            raise AsepriteMCPError("ASEPRITE_FAILED", message)
        return ProcessResult(process.returncode, stdout, stderr)

    @staticmethod
    async def _stop(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
