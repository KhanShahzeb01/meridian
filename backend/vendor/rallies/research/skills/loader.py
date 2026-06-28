"""Parse SKILL.md files (YAML frontmatter + markdown body)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path
    source: str
    instructions: str


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    path: Path
    source: str


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _split_frontmatter(content: str) -> tuple[dict, str]:
    match = _FRONTMATTER_RE.match(content)
    if not match:
        raise ValueError("SKILL.md missing YAML frontmatter")
    data = yaml.safe_load(match.group(1)) or {}
    body = content[match.end() :].strip()
    return data, body


def parse_skill_file(content: str, path: Path, source: str) -> Skill:
    data, instructions = _split_frontmatter(content)
    name = data.get("name")
    description = data.get("description")
    if not name or not isinstance(name, str):
        raise ValueError(f"Skill at {path} missing 'name' in frontmatter")
    if not description or not isinstance(description, str):
        raise ValueError(f"Skill at {path} missing 'description' in frontmatter")
    return Skill(
        name=name.strip(),
        description=description.strip(),
        path=path,
        source=source,
        instructions=instructions,
    )


def extract_skill_metadata(path: Path, source: str) -> SkillMetadata:
    content = path.read_text(encoding="utf-8")
    data, _ = _split_frontmatter(content)
    name = data.get("name")
    description = data.get("description")
    if not name or not isinstance(name, str):
        raise ValueError(f"Skill at {path} missing 'name' in frontmatter")
    if not description or not isinstance(description, str):
        raise ValueError(f"Skill at {path} missing 'description' in frontmatter")
    return SkillMetadata(
        name=name.strip(),
        description=description.strip(),
        path=path,
        source=source,
    )


def load_skill_from_path(path: Path, source: str) -> Skill:
    content = path.read_text(encoding="utf-8")
    return parse_skill_file(content, path, source)
