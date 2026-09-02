"""Typed, policy-enforcing adapter around the Aseprite CLI and Lua bridge."""

from __future__ import annotations
import logging
from ..errors import AsepriteMCPError
from ..models import HealthResult, SpriteInfo
from ..paths import SPRITE_INPUT_EXTENSIONS, sha256_file

logger = logging.getLogger(__name__)


from .runtime import AsepriteRuntime


class CoreService(AsepriteRuntime):
    """Core Aseprite operations."""

    async def health(self, server_version: str) -> HealthResult:
        logger.info("Running Aseprite health check server_version=%s", server_version)
        executable = self.settings.aseprite_executable
        if executable is None:
            logger.warning("Health check failed because no Aseprite executable was found")
            return HealthResult(
                ok=False,
                server_version=server_version,
                executable_path=None,
                aseprite_version=None,
                api_version=None,
                allowed_roots=[str(path) for path in self.settings.allowed_roots],
                timeout_seconds=self.settings.timeout_seconds,
                max_concurrency=self.settings.max_concurrency,
                execution_mode=self.execution_mode,
                bridge_temp_root=(
                    str(self.bridge_temp_root) if self.bridge_temp_root is not None else None
                ),
                error="ASEPRITE_NOT_FOUND: configure --aseprite or ASEPRITE_EXECUTABLE",
            )
        try:
            version_result = await self._run(["--version"], operation="version")
            bridge_health = await self._bridge("health", {})
            version = version_result.stdout.strip() or str(
                bridge_health.get("aseprite_version", "")
            )
            api_version = int(bridge_health["api_version"])
            logger.info(
                "Aseprite health check passed version=%s api_version=%d", version, api_version
            )
            return HealthResult(
                ok=True,
                server_version=server_version,
                executable_path=str(executable),
                aseprite_version=version,
                api_version=api_version,
                allowed_roots=[str(path) for path in self.settings.allowed_roots],
                timeout_seconds=self.settings.timeout_seconds,
                max_concurrency=self.settings.max_concurrency,
                execution_mode=self.execution_mode,
                bridge_temp_root=(
                    str(self.bridge_temp_root) if self.bridge_temp_root is not None else None
                ),
            )
        except AsepriteMCPError as exc:
            logger.warning(
                "Aseprite health check failed code=%s message=%s", exc.code, exc.message
            )
            return HealthResult(
                ok=False,
                server_version=server_version,
                executable_path=str(executable),
                aseprite_version=None,
                api_version=None,
                allowed_roots=[str(path) for path in self.settings.allowed_roots],
                timeout_seconds=self.settings.timeout_seconds,
                max_concurrency=self.settings.max_concurrency,
                execution_mode=self.execution_mode,
                bridge_temp_root=(
                    str(self.bridge_temp_root) if self.bridge_temp_root is not None else None
                ),
                error=str(exc),
            )

    async def inspect_sprite(
        self, source_path: str, *, include_palette_colors: bool = False
    ) -> SpriteInfo:
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        logger.info(
            "Inspecting sprite source=%s include_palette_colors=%s",
            source,
            include_palette_colors,
        )
        async with self._locked([source]):
            result = await self._bridge(
                "inspect",
                {
                    "source_path": self._process_path(source),
                    "include_palette_colors": include_palette_colors,
                },
            )
            result["source_path"] = str(source)
            result["sha256"] = sha256_file(source)
            sprite = SpriteInfo.model_validate(result)
            logger.info(
                "Sprite inspection completed source=%s size=%dx%d frames=%d",
                source,
                sprite.width,
                sprite.height,
                sprite.frame_count,
            )
            return sprite
