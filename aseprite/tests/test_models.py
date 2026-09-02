import pytest
from pydantic import ValidationError

from aseprite_mcp.models import PixelInput


def test_pixel_color_is_normalized() -> None:
    pixel = PixelInput(x=1, y=2, color="#aabbccdd")

    assert pixel.color == "#AABBCCDD"


@pytest.mark.parametrize("color", ["AABBCC", "#abcd", "#GG0000"])
def test_invalid_pixel_color_is_rejected(color: str) -> None:
    with pytest.raises(ValidationError):
        PixelInput(x=0, y=0, color=color)
