"""Universal AI agent harness and assistant-specific overlay templates."""

from __future__ import annotations

from pathlib import Path

from .presets import PresetConfig, load_user_store_files
from .templates import TEMPLATE_ALIASES, arch_layer_names

PROFILE_CONTEXT_SPECS: dict[str, dict[str, str]] = {
    "python-microservice": {
        "profile": "`python-microservice` — Python package scaffold (`src/$pkg_name/` layout)",
        "setup": "`python -m venv .venv && source .venv/bin/activate && pip install -e .` (install test and build tools with `pip install pytest build`)",
        "run": "`$pkg_name` or `python -m $pkg_name` (`python src/main.py` is a checkout convenience shim)",
        "test": "`pytest`",
        "build": "`python -m build`",
        "layout": (
            "- `pyproject.toml`, `requirements.txt`, `.env.example`, `.gitignore`, `Dockerfile`, `.github/workflows/ci.yml`, `README.md` — package metadata, dependencies, environment template, ignore rules, container build, and CI workflow\n"
            "- `src/$pkg_name/__init__.py`, `src/$pkg_name/main.py`, `src/$pkg_name/__main__.py` — installable package and module entrypoint\n"
            "- `src/main.py` — thin checkout convenience shim\n"
            "- `tests/test_$pkg_name.py` — starter test suite"
        ),
        "stack_hint": "Python >= 3.11 (`src/$pkg_name/` package layout, PEP 621 `pyproject.toml`, type annotations)",
    },
    "typescript": {
        "profile": "`typescript` — TypeScript Node.js service (`nodenext` module configuration)",
        "setup": "`npm install` (no lockfile is generated initially)",
        "run": "`npm start` (runs `node dist/index.js` after building)",
        "test": "Unavailable — no test runner or test script is configured in `package.json`",
        "build": "`npm run build` (compiles `src/index.ts` to `dist/index.js` via `tsc`)",
        "layout": (
            "- `package.json`, `tsconfig.json` — package metadata, build/start scripts, and TypeScript compiler configuration\n"
            "- `src/index.ts` — TypeScript entrypoint\n"
            "- `Dockerfile`, `.gitignore`, `README.md` — multi-stage container build, ignore rules, and project overview"
        ),
        "stack_hint": "TypeScript strict mode (`ES2022`, `nodenext` module resolution in `src/`, compiled output in `dist/`)",
    },
    "helm-chart": {
        "profile": "`helm-chart` — Helm v2 application chart scaffold",
        "setup": "Unavailable — no dependency install step; requires the `helm` CLI on `PATH`",
        "run": "Unavailable — local chart scaffold only; cluster deployment is not configured and `ghcr.io/example/$name` in `values.yaml` is an unverified placeholder image",
        "test": "`helm lint .`",
        "build": "`helm template $name .` (renders Kubernetes manifests locally without cluster access)",
        "layout": (
            "- `Chart.yaml`, `values.yaml`, `.helmignore` — chart metadata, default values, and packaging ignore rules\n"
            "- `templates/_helpers.tpl`, `templates/deployment.yaml`, `templates/service.yaml` — chart helpers and workload/service manifests\n"
            "- `.github/workflows/helm-lint.yml` — CI workflow for chart validation"
        ),
        "stack_hint": "Helm v2 chart (`Chart.yaml`, parameterized `values.yaml`, Kubernetes manifests in `templates/`)",
    },
    "none": {
        "profile": "`none` — Minimal agent-only repository without a language runtime or build toolchain",
        "setup": "Unavailable — no language runtime or package manager is configured",
        "run": "Unavailable — no application entrypoint is generated",
        "test": "Unavailable — no test runner is configured",
        "build": "Unavailable — no build system is configured",
        "layout": "- `README.md`, `.gitignore` — repository overview and ignore rules",
        "stack_hint": "Language-agnostic agent workspace (`AGENTS.md`, `$prompts_file`, `.remember/`, `.agents/skills/`)",
    },
}


_DEFAULT_REMEMBER_PATHS: tuple[str, ...] = (
    ".remember/MEMORY.md",
    ".remember/decisions.md",
)
_DEFAULT_SKILL_PATHS: tuple[str, ...] = (
    ".agents/skills/project-conventions/SKILL.md",
)


def _resolve_remember_paths(remember_files: list[str] | None) -> list[str]:
    if not remember_files or set(_DEFAULT_REMEMBER_PATHS) <= set(remember_files):
        return list(_DEFAULT_REMEMBER_PATHS)
    return list(dict.fromkeys(remember_files))


def _resolve_skill_paths(skill_files: list[str] | None) -> list[str]:
    if not skill_files or set(_DEFAULT_SKILL_PATHS) <= set(skill_files):
        return list(_DEFAULT_SKILL_PATHS)
    return list(dict.fromkeys(skill_files))


def _primary_memory_ref(remember_files: list[str] | None) -> str:
    paths = _resolve_remember_paths(remember_files)
    if ".remember/MEMORY.md" in paths:
        return ".remember/MEMORY.md"
    return paths[0]


def build_agents_md_template(
    lang: str = "none",
    *,
    arch: str = "modular",
    include_graphify: bool = True,
    remember_files: list[str] | None = None,
    skill_files: list[str] | None = None,
) -> str:
    """Build the AGENTS.md template with profile-resolved commands, layout, and boundaries."""
    resolved = TEMPLATE_ALIASES.get(lang, lang)
    spec = PROFILE_CONTEXT_SPECS.get(resolved, PROFILE_CONTEXT_SPECS["none"])

    rem_paths = _resolve_remember_paths(remember_files)
    sk_paths = _resolve_skill_paths(skill_files)

    harness_tokens = [
        "`AGENTS.md`",
        "`$prompts_file`",
        "`$outputs_dir/`",
        "`$scripts_dir/`",
        *(f"`{p}`" for p in rem_paths),
        *(f"`{p}`" for p in sk_paths),
        "`.agents/skills/`",
    ]
    if include_graphify:
        harness_tokens.append("`graphify-out/.gitkeep`")
    harness_line = ", ".join(harness_tokens)

    arch_dirs = arch_layer_names(resolved, arch)
    arch_layout_line = ""
    if arch_dirs:
        arch_tokens = ", ".join(f"`{d}`" for d in arch_dirs)
        arch_layout_line = f"- {arch_tokens} — {arch} architecture layer packages\n"

    rem_prose = ", ".join(f"`{p}`" for p in rem_paths)
    sk_prose = ", ".join(f"`{p}`" for p in sk_paths)

    graphify_section = ""
    if include_graphify:
        graphify_section = (
            "\n## Knowledge Graph (`graphify`)\n\n"
            "- Scaffolding creates `graphify-out/.gitkeep` as a directory placeholder only; it does not install the external `graphify` CLI or pre-populate a graph.\n"
            "- Only when a populated graph exists at `graphify-out/graph.json` and the external `graphify` CLI is installed (on `PATH` or `~/.local/bin/graphify`), prefer querying the graph before reading raw files:\n"
            '  - `graphify query "<question>"`\n'
            '  - `graphify path "<NodeA>" "<NodeB>"`\n'
            '  - `graphify explain "<concept>"`\n'
            "- If `graphify-out/wiki/index.md` exists, navigate it first.\n"
            "- When the external `graphify` CLI is installed, run `graphify update .` after modifying code files to populate or refresh `graphify-out/`.\n"
        )

    arch_desc = (
        f"`$arch` (scaffolded layer directories: {', '.join(f'`{d}`' for d in arch_dirs)})"
        if arch_dirs
        else "`$arch` (module organization convention)"
    )

    return (
        "# AGENTS.md — $name\n\n"
        "$description\n\n"
        "## Profile & Working Commands\n\n"
        f"- **Profile**: {spec['profile']}\n"
        f"- **Setup**: {spec['setup']}\n"
        f"- **Run**: {spec['run']}\n"
        f"- **Test**: {spec['test']}\n"
        f"- **Build**: {spec['build']}\n\n"
        "## Generated Project Layout\n\n"
        f"{spec['layout']}\n"
        f"{arch_layout_line}"
        f"- {harness_line} — shared agent instructions, prompt catalog, output/script directories, memory, and skills\n\n"
        "## Project Architecture & Layout\n\n"
        f"- **Architecture Style**: {arch_desc}\n"
        "- **Outputs Directory**: `$outputs_dir/` — place all generated artifacts, reports, and exports here.\n"
        "- **Scripts Directory**: `$scripts_dir/` — store helper, automation, and maintenance scripts here.\n"
        "- **Ordered Prompts File**: `$prompts_file` — maintain ordered prompts and reusable agent instructions here.\n"
        f"- **Persistent Memory**: `.remember/` — read {rem_prose} before starting work, and update them when key decisions are made.\n"
        f"- **Agent Skills**: `.agents/skills/` — project-specific reusable skills ({sk_prose}).\n\n"
        "## Change Boundaries & Hygiene\n\n"
        "- Use only the verified commands listed in **Profile & Working Commands** above; do not invent or assume unconfigured build, test, or runtime commands.\n"
        "- Keep generated outputs in `$outputs_dir/` and helper scripts in `$scripts_dir/` rather than mixing them into source packages.\n"
        "- Never commit `.env` or real credentials; keep only shareable templates (such as `.env.example`, `.env.sample`, or `.env.template`) tracked in version control.\n"
        f"{graphify_section}"
    )


AGENTS_MD_TEMPLATE = build_agents_md_template("none")


def build_prompts_md_template(
    *,
    include_graphify: bool = True,
    remember_files: list[str] | None = None,
) -> str:
    """Build the ordered prompts catalog template, conditionally including Graphify guidance."""
    primary_memory = _primary_memory_ref(remember_files)
    if include_graphify:
        p1_graph = ", and `graphify-out/` (when `graphify-out/graph.json` is populated)"
        p2_graph = ", and run `graphify update .` when the `graphify` CLI is available"
    else:
        p1_graph = ""
        p2_graph = ""
    return (
        "# Ordered Prompts Catalog — $name\n\n"
        "Keep project prompts ordered and versioned in this file.\n\n"
        "## 01. Architecture & Context Prompt\n"
        f"> Review `AGENTS.md`, `{primary_memory}`{p1_graph} before proposing changes. "
        "Follow the `$arch` architecture pattern and the profile commands in `AGENTS.md`. "
        "Put outputs in `$outputs_dir/` and scripts in `$scripts_dir/`.\n\n"
        "## 02. Feature Implementation Prompt\n"
        f"> Implement the requested feature following `$arch` boundaries, verify using "
        f"the profile commands documented in `AGENTS.md`{p2_graph}.\n"
    )


PROMPTS_MD_TEMPLATE = build_prompts_md_template(include_graphify=True)


def build_agent_overlays(
    *,
    lang: str = "none",
    arch: str = "modular",
    include_graphify: bool = True,
    remember_files: list[str] | None = None,
    skill_files: list[str] | None = None,
) -> dict[str, dict[str, str]]:
    """Build stack-aware assistant overlay templates referencing AGENTS.md."""
    resolved = TEMPLATE_ALIASES.get(lang, lang)
    spec = PROFILE_CONTEXT_SPECS.get(resolved, PROFILE_CONTEXT_SPECS["none"])
    stack_hint = spec["stack_hint"]
    arch_dirs = arch_layer_names(resolved, arch)
    arch_hint = (
        f"`$arch` (layers: {', '.join(f'`{d}`' for d in arch_dirs)})"
        if arch_dirs
        else "`$arch`"
    )

    rem_paths = _resolve_remember_paths(remember_files)
    primary_memory = _primary_memory_ref(remember_files)
    rem_list = ", ".join(f"`{p}`" for p in rem_paths)
    _ = _resolve_skill_paths(skill_files)

    claude_graph_line = (
        "- **Knowledge graph**: `graphify-out/` (placeholder until `graphify-out/graph.json` is populated; run `graphify update .` after code changes when `graphify` is installed)\n"
        if include_graphify
        else ""
    )
    copilot_graph_line = (
        "- Check `graphify-out/` when `graphify-out/graph.json` is populated (requires external `graphify` CLI).\n"
        if include_graphify
        else ""
    )
    codeassistant_graph_line = (
        "- **Graphify**: `graphify-out/` (placeholder until populated; see `AGENTS.md`)\n"
        if include_graphify
        else ""
    )

    return {
        "claude": {
            "CLAUDE.md": (
                "# CLAUDE.md — $name\n\n"
                f"Read and follow @AGENTS.md and @{primary_memory} at the start of every session.\n"
                "`AGENTS.md` defines the authoritative profile commands (setup, run, test, build), "
                "generated layout, and change boundaries.\n\n"
                "## Stack & Conventions\n"
                f"- **Stack**: {stack_hint}\n"
                f"- **Architecture**: {arch_hint}\n"
                "- **Outputs folder**: `$outputs_dir/`\n"
                "- **Scripts folder**: `$scripts_dir/`\n"
                "- **Ordered prompts**: `$prompts_file`\n"
                "- **Skills**: `.agents/skills/`\n"
                f"{claude_graph_line}"
            ),
            ".claude/settings.json": "{\n}\n",
        },
        "gh-copilot": {
            ".github/copilot-instructions.md": (
                "# GitHub Copilot Instructions — $name\n\n"
                "$description\n\n"
                "## Workspace Conventions\n"
                f"- Read `AGENTS.md` and `{primary_memory}` first; `AGENTS.md` is the single source of truth for profile setup, run, test, and build commands and layout.\n"
                f"- Stack profile: {stack_hint}.\n"
                f"- Follow the **{arch_hint}** architecture pattern.\n"
                "- Save generated outputs and reports in `$outputs_dir/`.\n"
                "- Place helper and automation scripts in `$scripts_dir/`.\n"
                "- Keep ordered prompts in `$prompts_file`.\n"
                "- Check `.agents/skills/` for domain skills.\n"
                f"{copilot_graph_line}"
            ),
            ".github/prompts/bootstrap.prompt.md": (
                "---\n"
                'description: "Context-aware task execution for $name"\n'
                "---\n\n"
                f"Review `AGENTS.md`, `{primary_memory}`, and `$prompts_file`.\n"
                "Use the profile commands and change boundaries documented in `AGENTS.md`.\n"
                "Ensure generated outputs go into `$outputs_dir/` and scripts go into `$scripts_dir/`.\n"
            ),
        },
        "codeassistant": {
            ".codeassistant/instructions.md": (
                "# CodeAssistant Instructions — $name\n\n"
                "- **Shared Context**: Read `AGENTS.md` for profile setup, run, test, and build commands and generated layout.\n"
                f"- **Stack**: {stack_hint}\n"
                f"- **Architecture**: {arch_hint}\n"
                "- **Outputs Directory**: `$outputs_dir/`\n"
                "- **Scripts Directory**: `$scripts_dir/`\n"
                "- **Prompts Log**: `$prompts_file`\n"
                f"- **Memory & Decisions**: {rem_list}\n"
                "- **Skills**: `.agents/skills/`\n"
                f"{codeassistant_graph_line}"
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
                f"- Read `AGENTS.md` and `{primary_memory}`; follow the profile commands and change boundaries in `AGENTS.md`.\n"
                f"- Stack: {stack_hint}.\n"
                f"- Follow {arch_hint} architecture.\n"
                "- Put outputs in `$outputs_dir/`, scripts in `$scripts_dir/`, and prompts in `$prompts_file`.\n"
            ),
        },
    }


AGENT_OVERLAYS: dict[str, dict[str, str]] = build_agent_overlays(include_graphify=True)

SUPPORTED_AGENTS: tuple[str, ...] = tuple(AGENT_OVERLAYS.keys())


def universal_harness_files(
    preset: PresetConfig,
    config_dir: Path | None = None,
    lang: str = "none",
    *,
    include_graphify: bool = True,
) -> dict[str, str]:
    """Return unrendered template bodies for the universal AI agent harness."""
    try:
        user_store = load_user_store_files(
            config_dir, include_graphify=include_graphify
        )
    except TypeError:
        user_store = load_user_store_files(config_dir)

    remember_files = sorted(p for p in user_store if p.startswith(".remember/"))
    skill_files = sorted(p for p in user_store if p.startswith(".agents/skills/"))

    files: dict[str, str] = {
        "AGENTS.md": build_agents_md_template(
            lang,
            arch=preset.arch,
            include_graphify=include_graphify,
            remember_files=remember_files,
            skill_files=skill_files,
        ),
        f"{preset.outputs_dir}/.gitkeep": "",
        f"{preset.scripts_dir}/.gitkeep": "",
        preset.prompts_file: build_prompts_md_template(
            include_graphify=include_graphify,
            remember_files=remember_files,
        ),
    }
    if include_graphify:
        files["graphify-out/.gitkeep"] = ""
    files.update(user_store)
    return files


def agent_overlay_files(
    agents: list[str],
    *,
    lang: str = "none",
    arch: str = "modular",
    include_graphify: bool = True,
    remember_files: list[str] | None = None,
    skill_files: list[str] | None = None,
) -> dict[str, str]:
    """Return unrendered template bodies for the selected `-a` assistant adapters."""
    overlays = build_agent_overlays(
        lang=lang,
        arch=arch,
        include_graphify=include_graphify,
        remember_files=remember_files,
        skill_files=skill_files,
    )
    out: dict[str, str] = {}
    for agent in agents:
        key = agent.strip().lower()
        if key not in overlays:
            available = ", ".join(SUPPORTED_AGENTS)
            raise KeyError(f"Unknown agent '{agent}'. Available: {available}")
        out.update(overlays[key])
    return out
