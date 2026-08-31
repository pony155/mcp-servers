"""Filesystem authorization and safe publication helpers."""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from .errors import AsepriteMCPError

SPRITE_INPUT_EXTENSIONS = frozenset({".ase", ".aseprite", ".gif", ".png"})
SPRITE_DOCUMENT_EXTENSIONS = frozenset({".ase", ".aseprite"})
RENDER_EXTENSIONS = frozenset({".gif", ".png"})


def _is_device_path(raw: str) -> bool:
    normalized = raw.replace("/", "\\").lower()
    return normalized.startswith(("\\\\.\\", "\\\\?\\globalroot\\", "\\device\\"))


class PathPolicy:
    """Authorize paths against canonical, explicitly configured roots."""

    def __init__(self, roots: tuple[Path, ...]) -> None:
        self.roots = tuple(root.resolve(strict=True) for root in roots)

    def _require_roots(self) -> None:
        if not self.roots:
            raise AsepriteMCPError(
                "PATH_NOT_ALLOWED",
                "No allowed roots are configured; start the server with --allow-root PATH",
            )

    def _authorize(self, path: Path) -> Path:
        self._require_roots()
        for root in self.roots:
            try:
                path.relative_to(root)
                return path
            except ValueError:
                continue
        raise AsepriteMCPError("PATH_NOT_ALLOWED", "Path is outside the configured roots")

    def existing_file(self, raw_path: str, *, extensions: frozenset[str] | None = None) -> Path:
        if _is_device_path(raw_path):
            raise AsepriteMCPError("PATH_NOT_ALLOWED", "Device paths are not allowed")
        candidate = Path(raw_path).expanduser()
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise AsepriteMCPError(
                "FILE_NOT_FOUND", f"Input file does not exist: {candidate}"
            ) from exc
        if not resolved.is_file():
            raise AsepriteMCPError("FILE_NOT_FOUND", f"Input is not a regular file: {candidate}")
        self._authorize(resolved)
        self._check_extension(resolved, extensions)
        return resolved

    def output_file(
        self,
        raw_path: str,
        *,
        extensions: frozenset[str] | None = None,
        overwrite: bool = False,
    ) -> Path:
        if _is_device_path(raw_path):
            raise AsepriteMCPError("PATH_NOT_ALLOWED", "Device paths are not allowed")
        candidate = Path(raw_path).expanduser()
        self._check_extension(candidate, extensions)
        parent = candidate.parent.resolve(strict=True)
        self._authorize(parent)
        resolved = parent / candidate.name
        if resolved.exists():
            if not resolved.is_file():
                raise AsepriteMCPError("PATH_NOT_ALLOWED", "Output is not a regular file")
            canonical = resolved.resolve(strict=True)
            self._authorize(canonical)
            if not overwrite:
                raise AsepriteMCPError(
                    "OUTPUT_EXISTS", "Output already exists; pass overwrite=true to replace it"
                )
            resolved = canonical
        return resolved

    @staticmethod
    def _check_extension(path: Path, extensions: frozenset[str] | None) -> None:
        if extensions is not None and path.suffix.lower() not in extensions:
            allowed = ", ".join(sorted(extensions))
            raise AsepriteMCPError(
                "UNSUPPORTED_FORMAT", f"Unsupported file extension; expected one of: {allowed}"
            )


def temporary_sibling(destination: Path) -> Path:
    """Return a unique sibling path that preserves the destination extension."""

    token = uuid.uuid4().hex
    return destination.with_name(f".{destination.stem}.{token}.tmp{destination.suffix}")


def publish_file(temporary: Path, destination: Path) -> None:
    """Atomically publish a completed sibling file."""

    os.replace(temporary, destination)


def sha256_file(path: Path) -> str:
    """Hash a file without loading it entirely into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
