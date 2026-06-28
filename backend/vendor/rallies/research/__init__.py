"""Additive research layer (Wave 1+). Does not replace rallies planner or slash commands."""

from .paths import (
    ensure_data_dir,
    rallies_data_dir,
    rules_path,
    scratchpad_dir,
    soul_path,
    tool_results_dir,
    web_fetch_cache_dir,
    project_skills_dir,
)
from .rules import ensure_default_rules_template, load_rules, rules_system_prefix
from .soul import ensure_default_soul_template, load_soul, soul_system_prefix
from .scratchpad import Scratchpad, ToolLimitConfig
from .session import ResearchSession
from .tool_registry import REGISTERED_TOOLS, build_compact_tool_descriptions
from .web import fetch_url
from .batch import parallel_quote_sec_bundle, bundle_to_text
from .tool_results import spill_if_large
from .skills import discover_skills, get_skill, build_skill_metadata_section
from .filing import fetch_filing_section, format_filing_section
from .meta import research_fetch, research_fetch_multi
from .microcompact import microcompact_messages
from .loop import ResearchLoop

__all__ = [
    "ResearchSession",
    "Scratchpad",
    "ToolLimitConfig",
    "REGISTERED_TOOLS",
    "build_compact_tool_descriptions",
    "load_rules",
    "rules_system_prefix",
    "ensure_default_rules_template",
    "load_soul",
    "soul_system_prefix",
    "ensure_default_soul_template",
    "ensure_data_dir",
    "rallies_data_dir",
    "rules_path",
    "soul_path",
    "scratchpad_dir",
    "tool_results_dir",
    "web_fetch_cache_dir",
    "project_skills_dir",
    "fetch_url",
    "parallel_quote_sec_bundle",
    "bundle_to_text",
    "spill_if_large",
    "discover_skills",
    "get_skill",
    "build_skill_metadata_section",
    "fetch_filing_section",
    "format_filing_section",
    "research_fetch",
    "research_fetch_multi",
    "microcompact_messages",
    "ResearchLoop",
]
