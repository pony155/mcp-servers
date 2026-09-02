"""Start the Aseprite MCP server from the repository checkout."""

from __future__ import annotations

import logging
import sys
from importlib import import_module
from pathlib import Path
from typing import Callable, cast

logger = logging.getLogger("mcp_servers.launcher")


def _configure_launcher_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s [pid=%(process)d]: %(message)s",
        stream=sys.stderr,
    )


def _server_main(project_root: Path) -> Callable[[], None]:
    """Find the Aseprite server in the supported repository layouts."""

    flattened_package = project_root / "aseprite" / "__main__.py"
    legacy_source = project_root / "servers" / "aseprite" / "src"

    if flattened_package.is_file():
        module_name = "aseprite.__main__"
        logger.info("Using flattened Aseprite server package: %s", flattened_package.parent)
    elif (legacy_source / "aseprite_mcp" / "__main__.py").is_file():
        sys.path.insert(0, str(legacy_source))
        module_name = "aseprite_mcp.__main__"
        logger.info("Using legacy Aseprite server source layout: %s", legacy_source)
    else:
        module_name = "aseprite_mcp.__main__"
        logger.info("No source package found; trying installed module %s", module_name)

    logger.debug("Importing Aseprite server entry point from %s", module_name)
    module = import_module(module_name)
    return cast(Callable[[], None], module.main)


def main() -> None:
    """Load and run the current Aseprite MCP server entry point."""

    _configure_launcher_logging()
    project_root = Path(__file__).resolve().parent
    logger.info("Starting MCP server launcher from %s", project_root)
    sys.path.insert(0, str(project_root))
    try:
        run_server = _server_main(project_root)
    except ModuleNotFoundError as exc:
        missing = exc.name or "an unknown dependency"
        logger.error("Unable to import Aseprite MCP server; missing module=%s", missing)
        raise SystemExit(
            "Unable to load the Aseprite MCP server "
            f"(missing {missing}). Activate the project virtual environment and install "
            "the dependencies declared in aseprite/pyproject.toml."
        ) from exc

    logger.info("Aseprite MCP entry point loaded; transferring control")
    run_server()


if __name__ == "__main__":
    main()
