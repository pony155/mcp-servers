import os
from pathlib import Path

import pytest

from aseprite_mcp.adapter import AsepriteAdapter
from aseprite_mcp.config import Settings
from aseprite_mcp.models import FrameDefinition, LayerDefinition, PixelInput
from aseprite_mcp.paths import sha256_file

pytestmark = pytest.mark.integration


def configured_executable() -> Path:
    raw = os.environ.get("ASEPRITE_EXECUTABLE")
    if not raw or not Path(raw).is_file():
        pytest.skip("ASEPRITE_EXECUTABLE is not configured")
    return Path(raw).resolve()


@pytest.mark.asyncio
async def test_create_inspect_edit_render_and_export(tmp_path: Path) -> None:
    adapter = AsepriteAdapter(
        Settings(aseprite_executable=configured_executable(), allowed_roots=(tmp_path,))
    )
    source = tmp_path / "source.aseprite"
    edited = tmp_path / "edited.aseprite"
    rendered = tmp_path / "rendered.png"
    sheet = tmp_path / "sheet.png"
    data = tmp_path / "sheet.json"

    created = await adapter.create_sprite(
        str(source),
        width=8,
        height=8,
        color_mode="rgb",
        layers=[LayerDefinition(name="Artwork")],
        frames=[FrameDefinition(duration_ms=120), FrameDefinition(duration_ms=80)],
        pixels=[PixelInput(x=1, y=1, color="#FF0000FF")],
        overwrite=False,
    )
    source_hash = sha256_file(source)

    inspected = await adapter.inspect_sprite(str(source), include_palette_colors=True)
    assert created.sprite.width == 8
    assert inspected.frame_count == 2
    assert inspected.layers[0].name == "Artwork"

    mutation = await adapter.set_pixels(
        str(source),
        str(edited),
        layer="Artwork",
        frame=1,
        pixels=[PixelInput(x=2, y=2, color="#00FF00FF")],
        overwrite=False,
        expected_source_hash=source_hash,
    )
    assert mutation.source_sha256 == source_hash
    assert sha256_file(source) == source_hash

    render_result = await adapter.render(
        str(edited),
        str(rendered),
        frame=1,
        tag=None,
        layers=[],
        scale=2,
        overwrite=False,
    )
    assert render_result.byte_size > 0

    sheet_result = await adapter.export_sprite_sheet(
        str(edited),
        str(sheet),
        str(data),
        layout="horizontal",
        tag=None,
        layers=[],
        trim=False,
        extrude=False,
        border_padding=0,
        shape_padding=0,
        inner_padding=0,
        overwrite=False,
    )
    assert sheet_result.frame_count == 2
    assert sheet.is_file()
    assert data.is_file()
