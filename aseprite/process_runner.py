"""Bounded, cancellable Aseprite child-process execution."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .errors import AsepriteMCPError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


class ProcessRunner:
    def __init__(self, timeout_seconds: float, max_capture_bytes: int) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_capture_bytes = max_capture_bytes

    async def run(
        self, executable: Path, arguments: list[str], *, operation: str = "aseprite"
    ) -> ProcessResult:
        started_at = time.monotonic()
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        logger.info(
            "Launching Aseprite process operation=%s executable=%s argument_count=%d",
            operation,
            executable,
            len(arguments),
        )
        logger.debug("Aseprite arguments operation=%s arguments=%r", operation, arguments)
        try:
            process = await asyncio.create_subprocess_exec(
                str(executable),
                *arguments,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=creationflags,
            )
        except OSError as exc:
            logger.error(
                "Failed to start Aseprite process operation=%s error_type=%s message=%s",
                operation,
                type(exc).__name__,
                exc,
            )
            raise AsepriteMCPError(
                "ASEPRITE_FAILED", f"Unable to start Aseprite: {exc}"
            ) from exc
        logger.debug("Aseprite process started operation=%s pid=%s", operation, process.pid)
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            elapsed = time.monotonic() - started_at
            logger.error(
                "Aseprite process timed out operation=%s pid=%s elapsed=%.3fs",
                operation,
                process.pid,
                elapsed,
            )
            await self._stop(process)
            raise AsepriteMCPError(
                "OPERATION_TIMEOUT",
                f"Aseprite exceeded the {self.timeout_seconds:g}-second timeout",
            ) from exc
        except asyncio.CancelledError:
            logger.warning(
                "Aseprite process cancelled operation=%s pid=%s", operation, process.pid
            )
            await self._stop(process)
            raise

        elapsed = time.monotonic() - started_at
        captured_size = len(stdout_bytes) + len(stderr_bytes)
        if captured_size > self.max_capture_bytes:
            logger.error(
                "Aseprite diagnostics exceeded limit operation=%s pid=%s "
                "captured_bytes=%d limit=%d",
                operation,
                process.pid,
                captured_size,
                self.max_capture_bytes,
            )
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
            logger.error(
                "Aseprite process failed operation=%s pid=%s exit_code=%s "
                "elapsed=%.3fs diagnostic=%s",
                operation,
                process.pid,
                process.returncode,
                elapsed,
                diagnostic or "none",
            )
            raise AsepriteMCPError("ASEPRITE_FAILED", message)
        logger.info(
            "Aseprite process completed operation=%s pid=%s exit_code=%s "
            "elapsed=%.3fs stdout_bytes=%d stderr_bytes=%d",
            operation,
            process.pid,
            process.returncode,
            elapsed,
            len(stdout_bytes),
            len(stderr_bytes),
        )
        if stdout.strip():
            logger.debug("Aseprite stdout operation=%s: %s", operation, stdout.strip())
        if stderr.strip():
            logger.debug("Aseprite stderr operation=%s: %s", operation, stderr.strip())
        return ProcessResult(process.returncode, stdout, stderr)

    @staticmethod
    async def _stop(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        logger.debug("Terminating Aseprite process pid=%s", process.pid)
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning(
                "Aseprite process did not terminate promptly; killing pid=%s", process.pid
            )
            process.kill()
            await process.wait()
