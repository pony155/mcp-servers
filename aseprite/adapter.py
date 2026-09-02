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
    ModularService,
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
    ModularService,
):
    """Expose the stable adapter API while implementations live by domain."""

    pass
