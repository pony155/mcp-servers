"""Compatibility facade over domain-organized Aseprite services."""

from .services import (
    CoreService,
    PixelsService,
    DocumentsService,
    AnimationService,
    PalettesService,
    TilesService,
    ExportService,
    ValidationService,
    CombatService,
)


class AsepriteAdapter(
    CoreService,
    PixelsService,
    DocumentsService,
    AnimationService,
    PalettesService,
    TilesService,
    ExportService,
    ValidationService,
    CombatService,
):
    """Expose the stable adapter API while implementations live by domain."""

    pass
