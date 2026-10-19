"""Universal AI agent harness and assistant-specific overlay templates."""

from __future__ import annotations

from pathlib import Path

from .presets import PresetConfig, load_user_store_files

AGENTS_MD_TEMPLATE = """\
# AGENTS.md — $name

$description

## Project Architecture & Layout

- **Architecture Style**: `$arch`
- **Outputs Directory**: `$outputs_dir/` — place all generated artifacts, reports, and exports here.
- **Scripts Directory**: `$scripts_dir/` — store helper, automation, and maintenance scripts here.
- **Ordered Prompts File**: `$prompts_file` — maintain ordered prompts and reusable agent instructions here.
- **Persistent Memory**: `.remember/` — read `.remember/MEMORY.md` and `.remember/decisions.md` before starting work, and update them when key decisions are made.
- **Agent Skills**: `.agents/skills/` — project-specific reusable skills.

## Knowledge Graph (`graphify`)

- When `graphify-out/graph.json` exists, prefer querying the graph before reading raw files:
  - `graphify query "<question>"`
  - `graphify path "<NodeA>" "<NodeB>"`
  - `graphify explain "<concept>"`
- If `graphify-out/wiki/index.md` exists, navigate it first.
- After modifying code files, run `graphify update .` to keep `graphify-out/` current.
"""

PROMPTS_MD_TEMPLATE = """\
# Ordered Prompts Catalog — $name

Keep project prompts ordered and versioned in this file.

## 01. Architecture & Context Prompt
> Review `AGENTS.md`, `.remember/MEMORY.md`, and `graphify-out/` before proposing changes. Follow the `$arch` architecture pattern. Put outputs in `$outputs_dir/` and scripts in `$scripts_dir/`.

## 02. Feature Implementation Prompt
> Implement the requested feature following `$arch` boundaries, add unit tests, and run `graphify update .` when finished.
"""

AGENT_OVERLAYS: dict[str, dict[str, str]] = {
    "claude": {
        "CLAUDE.md": (
            "# CLAUDE.md — $name\n\n"
            "Read and follow @AGENTS.md and @.remember/MEMORY.md at the start of every session.\n\n"
            "## Quick Conventions\n"
            "- **Architecture**: `$arch`\n"
            "- **Outputs folder**: `$outputs_dir/`\n"
            "- **Scripts folder**: `$scripts_dir/`\n"
            "- **Ordered prompts**: `$prompts_file`\n"
            "- **Skills**: `.agents/skills/`\n"
            "- **Knowledge graph**: `graphify-out/` (run `graphify update .` after code changes)\n"
        ),
        ".claude/settings.json": "{\n}\n",
    },
    "gh-copilot": {
        ".github/copilot-instructions.md": (
            "# GitHub Copilot Instructions — $name\n\n"
            "$description\n\n"
            "## Workspace Conventions\n"
            "- Follow the **$arch** architecture pattern.\n"
            "- Read `AGENTS.md` and `.remember/MEMORY.md` for project context and decisions.\n"
            "- Save generated outputs and reports in `$outputs_dir/`.\n"
            "- Place helper and automation scripts in `$scripts_dir/`.\n"
            "- Keep ordered prompts in `$prompts_file`.\n"
            "- Check `.agents/skills/` for domain skills and `graphify-out/` for the project graph.\n"
        ),
        ".github/prompts/bootstrap.prompt.md": (
            "---\n"
            'description: "Context-aware task execution for $name"\n'
            "---\n\n"
            "Review `AGENTS.md`, `.remember/MEMORY.md`, and `$prompts_file`.\n"
            "Ensure generated outputs go into `$outputs_dir/` and scripts go into `$scripts_dir/`.\n"
        ),
    },
    "codeassistant": {
        ".codeassistant/instructions.md": (
            "# CodeAssistant Instructions — $name\n\n"
            "- **Architecture**: `$arch`\n"
            "- **Outputs Directory**: `$outputs_dir/`\n"
            "- **Scripts Directory**: `$scripts_dir/`\n"
            "- **Prompts Log**: `$prompts_file`\n"
            "- **Memory & Decisions**: `.remember/MEMORY.md`, `.remember/decisions.md`\n"
            "- **Skills**: `.agents/skills/`\n"
            "- **Graphify**: `graphify-out/` (refer to `AGENTS.md`)\n"
        ),
    },
    "cursor": {
        ".cursor/rules/project.mdc": (
            "---\n"
            'description: "Core project architecture and directory rules for $name"\n'
            'globs: "**/*"\n'
            "alwaysApply: true\n"
            "---\n\n"
            "# $name Rules\n\n"
            "- Follow `$arch` architecture.\n"
            "- Read `AGENTS.md` and `.remember/MEMORY.md`.\n"
            "- Put outputs in `$outputs_dir/`, scripts in `$scripts_dir/`, and prompts in `$prompts_file`.\n"
        ),
    },
}

SUPPORTED_AGENTS: tuple[str, ...] = tuple(AGENT_OVERLAYS.keys())


def universal_harness_files(
    preset: PresetConfig, config_dir: Path | None = None
) -> dict[str, str]:
    """Return unrendered template bodies for the universal AI agent harness."""
    files: dict[str, str] = {
        "AGENTS.md": AGENTS_MD_TEMPLATE,
        "graphify-out/.gitkeep": "",
        f"{preset.outputs_dir}/.gitkeep": "",
        f"{preset.scripts_dir}/.gitkeep": "",
        preset.prompts_file: PROMPTS_MD_TEMPLATE,
    }
    files.update(load_user_store_files(config_dir))
    return files


def agent_overlay_files(agents: list[str]) -> dict[str, str]:
    """Return unrendered template bodies for the selected `-a` assistant adapters."""
    out: dict[str, str] = {}
    for agent in agents:
        key = agent.strip().lower()
        if key not in AGENT_OVERLAYS:
            available = ", ".join(SUPPORTED_AGENTS)
            raise KeyError(f"Unknown agent '{agent}'. Available: {available}")
        out.update(AGENT_OVERLAYS[key])
    return out
