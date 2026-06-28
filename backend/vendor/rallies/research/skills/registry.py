"""Discover SKILL.md workflows from builtin + .rallies/skills/."""

from __future__ import annotations

from pathlib import Path

from ..paths import project_skills_dir
from .loader import Skill, SkillMetadata, load_skill_from_path, extract_skill_metadata

_BUILTIN_DIR = Path(__file__).resolve().parent / "builtin"

_SKILL_DIRS: list[tuple[Path, str]] = [
    (_BUILTIN_DIR, "builtin"),
    (project_skills_dir(), "project"),
]

_metadata_cache: dict[str, SkillMetadata] | None = None


def _scan_directory(dir_path: Path, source: str) -> list[SkillMetadata]:
    if not dir_path.is_dir():
        return []
    found: list[SkillMetadata] = []
    for entry in sorted(dir_path.iterdir()):
        if not entry.is_dir():
            continue
        skill_file = entry / "SKILL.md"
        if not skill_file.is_file():
            continue
        try:
            found.append(extract_skill_metadata(skill_file, source))
        except (ValueError, OSError):
            continue
    return found


def discover_skills(*, refresh: bool = False) -> list[SkillMetadata]:
    global _metadata_cache
    if _metadata_cache is not None and not refresh:
        return list(_metadata_cache.values())
    merged: dict[str, SkillMetadata] = {}
    for dir_path, source in _SKILL_DIRS:
        for meta in _scan_directory(dir_path, source):
            merged[meta.name] = meta
    _metadata_cache = merged
    return list(merged.values())


def get_skill(name: str) -> Skill | None:
    discover_skills()
    if not _metadata_cache:
        return None
    key = name.strip().lower()
    meta = _metadata_cache.get(key)
    if meta is None:
        for candidate in _metadata_cache.values():
            if candidate.name.lower() == key or candidate.path.parent.name.lower() == key:
                meta = candidate
                break
    if meta is None:
        return None
    return load_skill_from_path(meta.path, meta.source)


def list_skill_names() -> list[str]:
    return [s.name for s in discover_skills()]


def build_skill_metadata_section() -> str:
    skills = discover_skills()
    if not skills:
        return "No skills available."
    lines = [f"- **{s.name}**: {s.description}" for s in skills]
    return "\n".join(lines)


_SKILL_TRIGGERS: list[tuple[str, tuple[str, ...]]] = [
    ("write-memo", ("memo", "thesis", "writeup", "write up", "pitch", "long write", "short write")),
    ("dcf-valuation", ("dcf", "fair value", "intrinsic value", "price target", "undervalued", "overvalued")),
    ("compare-equities", ("compare", " versus ", " vs ", " vs.", "which is better", "peer", "relative")),
    ("earnings-digest", ("earnings", "beat", "miss", "guidance", "quarterly result", "preview")),
    ("sec-risk-review", ("risk factor", "10-k risk", "downside", "what could go wrong", "regulatory risk")),
    (
        "fred-economic-data",
        (
            "fred",
            "gdp",
            "unemployment",
            "inflation",
            "cpi",
            "interest rate",
            "fed funds",
            "treasury yield",
            "macro outlook",
            "recession",
            "economic indicator",
        ),
    ),
    (
        "edgartools",
        (
            "10-k",
            "10-q",
            "8-k",
            "sec filing",
            "form 4",
            "13f",
            " edgar",
            "md&a",
            "mda",
            "proxy statement",
            "xbrl",
            "annual report",
            "quarterly report",
        ),
    ),
    (
        "hedgefundmonitor",
        (
            "hedge fund",
            "form pf",
            "systemic risk",
            "repo market",
            "ofr",
            "financial stability",
            "hedge fund leverage",
            "sponsored repo",
        ),
    ),
    (
        "statistical-analyst",
        (
            "a/b test",
            "a/b ",
            "hypothesis test",
            "p-value",
            "p value",
            "significance",
            "sample size",
            "confidence interval",
            "effect size",
            "statistically significant",
            "experiment result",
            "bonferroni",
        ),
    ),
]

# sec-risk-review vs edgartools: prefer sec-risk-review for narrow risk-only asks
_SKILL_PRIORITY: dict[str, int] = {
    "sec-risk-review": 10,
    "edgartools": 5,
}


def suggest_skills_for_query(query: str, *, max_skills: int = 3) -> list[str]:
    """Keyword match for /research — suggests skills to load_skill first."""
    low = f" {query.lower()} "
    matched: list[str] = []
    for name, keywords in _SKILL_TRIGGERS:
        if any(kw in low for kw in keywords):
            matched.append(name)
    if "risk factor" in low or "10-k risk" in low:
        if "edgartools" in matched and "sec-risk-review" not in matched:
            matched.insert(0, "sec-risk-review")
    matched.sort(key=lambda n: -_SKILL_PRIORITY.get(n, 0))
    seen: set[str] = set()
    ordered: list[str] = []
    for name in matched:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered[:max_skills]


def clear_skill_cache() -> None:
    global _metadata_cache
    _metadata_cache = None
