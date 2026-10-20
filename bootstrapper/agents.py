"""Universal AI agent harness and assistant-specific overlay templates."""

from __future__ import annotations

from pathlib import Path

from .presets import PresetConfig, load_user_store_files
from .templates import TEMPLATE_ALIASES

PROFILE_CONTEXT_SPECS: dict[str, dict[str, str]] = {
    "python-microservice": {
        "profile": "`python-microservice` — Python starter package (`src/appstarter/` layout; starter point, not a production service)",
        "setup": "`python -m venv .venv && source .venv/bin/activate && pip install -e .` (install test and build tools with `pip install pytest build`)",
        "run": "`appstarter` or `python -m appstarter` (`python src/main.py` is a checkout-only compatibility shim)",
        "test": "`pytest`",
        "build": "`python -m build`",
        "layout": (
            "- `pyproject.toml`, `requirements.txt`, `.env.example`, `.gitignore`, `Dockerfile`, `.github/workflows/ci.yml`, `README.md` — package metadata, dependencies, environment template, ignore rules, container build, and CI workflow\n"
            "- `src/appstarter/__init__.py`, `src/appstarter/main.py`, `src/appstarter/__main__.py` — installable package and module entrypoint\n"
            "- `src/main.py` — thin checkout-only compatibility shim\n"
            "- `tests/test_appstarter.py` — starter test suite"
        ),
    },
    "typescript": {
        "profile": "`typescript` — TypeScript Node.js starter (`nodenext` module configuration)",
        "setup": "`npm install` (no lockfile is generated initially)",
        "run": "`npm start` (runs `node dist/index.js` after building)",
        "test": "Unavailable — no test runner or test script is configured in `package.json`",
        "build": "`npm run build` (compiles `src/index.ts` to `dist/index.js` via `tsc`)",
        "layout": (
            "- `package.json`, `tsconfig.json` — package metadata, build/start scripts, and TypeScript compiler configuration\n"
            "- `src/index.ts` — TypeScript entrypoint\n"
            "- `Dockerfile`, `.gitignore`, `README.md` — multi-stage container build, ignore rules, and project overview"
        ),
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
    },
    "rails": {
        "profile": "`rails` — **Experimental** layout sketch only (not a runnable Rails application and not `rails new` output)",
        "setup": "Unavailable — incomplete skeleton missing `config/boot.rb`, `config/environment.rb`, `config/routes.rb`, `bin/rails`, and `Rakefile`; requires Ruby >= 3.1 and `bundle install` only after completing the application",
        "run": "Unavailable — experimental layout does not boot an application server as generated",
        "test": "Unavailable — no test suite is generated (syntax-only check on generated Ruby files: `ruby -c config/application.rb && ruby -c app/controllers/application_controller.rb`)",
        "build": "Unavailable — no build step is configured",
        "layout": (
            "- `Gemfile`, `config.ru` — dependency declarations and Rack entrypoint sketch\n"
            "- `config/application.rb`, `app/controllers/application_controller.rb` — application module and base controller\n"
            "- `README.md` — experimental scope and missing preparation checklist"
        ),
    },
    "none": {
        "profile": "`none` — Minimal agent-only repository without a language runtime or build toolchain",
        "setup": "Unavailable — no language runtime or package manager is configured",
        "run": "Unavailable — no application entrypoint is generated",
        "test": "Unavailable — no test runner is configured",
        "build": "Unavailable — no build system is configured",
        "layout": "- `README.md`, `.gitignore` — repository overview and ignore rules",
    },
}


def build_agents_md_template(lang: str = "none") -> str:
    """Build the AGENTS.md template with profile-resolved commands, layout, and boundaries."""
    resolved = TEMPLATE_ALIASES.get(lang, lang)
    spec = PROFILE_CONTEXT_SPECS.get(resolved, PROFILE_CONTEXT_SPECS["none"])
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
        "- `AGENTS.md`, `$prompts_file`, `$outputs_dir/`, `$scripts_dir/`, `.remember/MEMORY.md`, `.remember/decisions.md`, `.agents/skills/` — shared agent instructions, prompt catalog, output/script directories, memory, and skills\n\n"
        "## Project Architecture & Layout\n\n"
        "- **Architecture Style**: `$arch` (instructional convention preference for organizing modules and boundaries)\n"
        "- **Outputs Directory**: `$outputs_dir/` — place all generated artifacts, reports, and exports here.\n"
        "- **Scripts Directory**: `$scripts_dir/` — store helper, automation, and maintenance scripts here.\n"
        "- **Ordered Prompts File**: `$prompts_file` — maintain ordered prompts and reusable agent instructions here.\n"
        "- **Persistent Memory**: `.remember/` — read `.remember/MEMORY.md` and `.remember/decisions.md` before starting work, and update them when key decisions are made.\n"
        "- **Agent Skills**: `.agents/skills/` — project-specific reusable skills.\n\n"
        "## Change Boundaries & Hygiene\n\n"
        "- Use only the verified commands listed in **Profile & Working Commands** above; do not invent or assume unconfigured build, test, or runtime commands.\n"
        "- Keep generated outputs in `$outputs_dir/` and helper scripts in `$scripts_dir/` rather than mixing them into source packages.\n"
        "- Never commit `.env` or real credentials; keep only shareable templates (such as `.env.example`) tracked in version control.\n\n"
        "## Knowledge Graph (`graphify`)\n\n"
        "- When `graphify-out/graph.json` exists, prefer querying the graph before reading raw files:\n"
        '  - `graphify query "<question>"`\n'
        '  - `graphify path "<NodeA>" "<NodeB>"`\n'
        '  - `graphify explain "<concept>"`\n'
        "- If `graphify-out/wiki/index.md` exists, navigate it first.\n"
        "- After modifying code files, run `graphify update .` to keep `graphify-out/` current.\n"
    )


AGENTS_MD_TEMPLATE = build_agents_md_template("none")

PROMPTS_MD_TEMPLATE = """\
# Ordered Prompts Catalog — $name

Keep project prompts ordered and versioned in this file.

## 01. Architecture & Context Prompt
> Review `AGENTS.md`, `.remember/MEMORY.md`, and `graphify-out/` before proposing changes. Follow the `$arch` architecture pattern and the profile commands in `AGENTS.md`. Put outputs in `$outputs_dir/` and scripts in `$scripts_dir/`.

## 02. Feature Implementation Prompt
> Implement the requested feature following `$arch` boundaries, verify using the profile commands documented in `AGENTS.md`, and run `graphify update .` when finished.
"""

AGENT_OVERLAYS: dict[str, dict[str, str]] = {
    "claude": {
        "CLAUDE.md": (
            "# CLAUDE.md — $name\n\n"
            "Read and follow @AGENTS.md and @.remember/MEMORY.md at the start of every session.\n"
            "`AGENTS.md` defines the authoritative profile commands (setup, run, test, build), "
            "generated layout, and change boundaries.\n\n"
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
            "- Read `AGENTS.md` and `.remember/MEMORY.md` first; `AGENTS.md` is the single source of truth for profile setup, run, test, and build commands and layout.\n"
            "- Follow the **$arch** architecture pattern.\n"
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
            "Use the profile commands and change boundaries documented in `AGENTS.md`.\n"
            "Ensure generated outputs go into `$outputs_dir/` and scripts go into `$scripts_dir/`.\n"
        ),
    },
    "codeassistant": {
        ".codeassistant/instructions.md": (
            "# CodeAssistant Instructions — $name\n\n"
            "- **Shared Context**: Read `AGENTS.md` for profile setup, run, test, and build commands and generated layout.\n"
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
            "- Read `AGENTS.md` and `.remember/MEMORY.md`; follow the profile commands and change boundaries in `AGENTS.md`.\n"
            "- Follow `$arch` architecture.\n"
            "- Put outputs in `$outputs_dir/`, scripts in `$scripts_dir/`, and prompts in `$prompts_file`.\n"
        ),
    },
}

SUPPORTED_AGENTS: tuple[str, ...] = tuple(AGENT_OVERLAYS.keys())


def universal_harness_files(
    preset: PresetConfig,
    config_dir: Path | None = None,
    lang: str = "none",
) -> dict[str, str]:
    """Return unrendered template bodies for the universal AI agent harness."""
    files: dict[str, str] = {
        "AGENTS.md": build_agents_md_template(lang),
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
