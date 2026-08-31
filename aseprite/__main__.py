"""Console entry point for the stdio MCP server."""

from __future__ import annotations

import logging
import sys

from .config import parse_settings
from .server import build_server


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    settings = parse_settings()
    server = build_server(settings)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
