from pathlib import Path

import pytest

from aseprite_mcp.errors import AsepriteMCPError
from aseprite_mcp.paths import SPRITE_DOCUMENT_EXTENSIONS, PathPolicy, temporary_sibling


def test_existing_file_inside_root(tmp_path: Path) -> None:
    sprite = tmp_path / "hero.aseprite"
    sprite.write_bytes(b"fixture")
    policy = PathPolicy((tmp_path,))

    assert (
        policy.existing_file(str(sprite), extensions=SPRITE_DOCUMENT_EXTENSIONS) == sprite.resolve()
    )


def test_existing_file_outside_root_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    sprite = tmp_path / "hero.aseprite"
    sprite.write_bytes(b"fixture")
    policy = PathPolicy((root,))

    with pytest.raises(AsepriteMCPError, match="PATH_NOT_ALLOWED"):
        policy.existing_file(str(sprite), extensions=SPRITE_DOCUMENT_EXTENSIONS)


def test_output_requires_explicit_overwrite(tmp_path: Path) -> None:
    sprite = tmp_path / "hero.aseprite"
    sprite.write_bytes(b"fixture")
    policy = PathPolicy((tmp_path,))

    with pytest.raises(AsepriteMCPError, match="OUTPUT_EXISTS"):
        policy.output_file(str(sprite), extensions=SPRITE_DOCUMENT_EXTENSIONS)

    assert (
        policy.output_file(str(sprite), extensions=SPRITE_DOCUMENT_EXTENSIONS, overwrite=True)
        == sprite.resolve()
    )


def test_temporary_sibling_preserves_extension(tmp_path: Path) -> None:
    output = tmp_path / "hero.aseprite"
    temporary = temporary_sibling(output)

    assert temporary.parent == output.parent
    assert temporary.suffix == ".aseprite"
    assert temporary != output
