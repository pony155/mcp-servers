"""Generate the checked-in skill catalog using only the Python standard library."""

from __future__ import annotations

import json
from pathlib import Path


FAMILIES = {
    "foundation": {
        "aseprite-concept-to-sprite",
        "aseprite-sprite-production",
    },
    "animation": {
        "aseprite-animation-cleanup",
        "aseprite-animation-event-authoring",
        "aseprite-animation-review",
        "aseprite-character-animation-set",
        "aseprite-cutscene-animation-production",
        "aseprite-directional-animation",
        "aseprite-fighting-game-animation",
        "aseprite-looping-background-production",
        "aseprite-modular-character-production",
        "aseprite-platformer-character-production",
        "aseprite-portrait-expression-production",
        "aseprite-top-down-character-production",
        "aseprite-vfx-production",
    },
    "color-and-qa": {
        "aseprite-accessibility-review",
        "aseprite-color-managed-export",
        "aseprite-color-variant-production",
        "aseprite-palette-cycle-production",
        "aseprite-palette-design",
        "aseprite-pixel-art-qa",
        "aseprite-pixel-art-restoration",
        "aseprite-retro-hardware-constraint-production",
    },
    "tiles-and-world": {
        "aseprite-autotile-authoring",
        "aseprite-environment-prop-production",
        "aseprite-isometric-tile-production",
        "aseprite-tile-metadata-authoring",
        "aseprite-tileset-production",
    },
    "ui-and-fonts": {
        "aseprite-bitmap-font-production",
        "aseprite-nine-slice-ui-production",
        "aseprite-rpg-icon-set-production",
        "aseprite-ui-sprite-production",
    },
    "export-and-pipeline": {
        "aseprite-atlas-production",
        "aseprite-batch-asset-pipeline",
        "aseprite-collision-shape-authoring",
        "aseprite-engine-export-profile",
        "aseprite-game-export",
        "aseprite-release-asset-audit",
    },
}

PROFILE_BY_FAMILY = {
    "foundation": "sprite",
    "animation": "animation",
    "color-and-qa": "qa",
    "tiles-and-world": "tiles",
    "ui-and-fonts": "sprite",
    "export-and-pipeline": "export",
}


def frontmatter(path: Path) -> tuple[str, str]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"missing frontmatter: {path}")
    values: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            break
        key, separator, value = line.partition(":")
        if separator:
            values[key.strip()] = value.strip()
    return values["name"], values["description"]


def main() -> None:
    root = Path(__file__).parent
    family_by_skill = {
        skill: family for family, skills in FAMILIES.items() for skill in skills
    }
    directories = sorted(
        path for path in root.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()
    )
    names = {path.name for path in directories}
    if names != set(family_by_skill):
        raise ValueError(
            f"skill family assignment mismatch: unassigned={names-set(family_by_skill)} "
            f"missing={set(family_by_skill)-names}"
        )
    entries = []
    for directory in directories:
        name, description = frontmatter(directory / "SKILL.md")
        if name != directory.name:
            raise ValueError(f"skill name does not match directory: {directory}")
        family = family_by_skill[name]
        entries.append(
            {
                "name": name,
                "family": family,
                "recommended_tool_profile": PROFILE_BY_FAMILY[family],
                "description": description,
                "path": f"{name}/SKILL.md",
            }
        )
    output = {"schema_version": 1, "skill_count": len(entries), "skills": entries}
    (root / "catalog.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
