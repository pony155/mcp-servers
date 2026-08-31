"""Console entry point for the stdio MCP server."""

from __future__ import annotations

import logging
import platform
import sys

from .config import parse_settings
from .errors import AsepriteMCPError
from .server import build_server

logger = logging.getLogger(__name__)


def _configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(name)s [pid=%(process)d]: %(message)s",
        stream=sys.stderr,
        force=True,
    )


def main() -> None:
    _configure_logging()
    logger.info("Parsing Aseprite MCP server configuration")
    try:
        settings = parse_settings()
    except AsepriteMCPError as exc:
        logger.error("Configuration failed code=%s message=%s", exc.code, exc.message)
        raise SystemExit(2) from exc
    _configure_logging(settings.log_level)
    logger.info(
        "Starting Aseprite MCP server on Python %s (%s)",
        platform.python_version(),
        sys.platform,
    )
    logger.info(
        "Configuration: executable=%s roots=%d requested_mode=%s timeout=%ss concurrency=%d",
        settings.aseprite_executable or "not found",
        len(settings.allowed_roots),
        settings.execution_mode,
        f"{settings.timeout_seconds:g}",
        settings.max_concurrency,
    )
    for root in settings.allowed_roots:
        logger.debug("Authorized filesystem root: %s", root)
    logger.debug(
        "Bridge temp root=%s max_capture_bytes=%d log_level=%s",
        settings.bridge_temp_root or "automatic",
        settings.max_capture_bytes,
        settings.log_level,
    )
    server = build_server(settings)
    logger.info("MCP stdio transport is starting; protocol messages use stdout")
    try:
        server.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Aseprite MCP server interrupted by user")
    except Exception as exc:
        logger.critical(
            "Aseprite MCP server stopped unexpectedly error_type=%s message=%s",
            type(exc).__name__,
            exc,
        )
        raise
    finally:
        logger.info("Aseprite MCP server stopped")


if __name__ == "__main__":
    main()
