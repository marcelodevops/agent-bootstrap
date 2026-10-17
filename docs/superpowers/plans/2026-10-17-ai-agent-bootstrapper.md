# AI Agent Project Bootstrapper (`projboot`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `projboot` AI-agent-first project bootstrapper that composes base language templates, customizable workflow presets (`~/.config/projboot/`), a universal agent harness (`AGENTS.md`, `graphify-out/`, `.remember/`, `.agents/skills/`, `PROMPTS.md`), and assistant-specific overlays (`claude`, `gh-copilot`, `codeassistant`, `cursor`) with local-first scaffolding and optional GitHub remote creation.

**Architecture:** A layered file composition pipeline (`presets.py` -> `agents.py` -> `composer.py` -> `cli.py`) that merges base language templates, user store templates (`~/.config/projboot/skills` and `remember`), universal agent harness files, and assistant adapter files into a `dict[str, str]` manifest rendered via `string.Template.safe_substitute`. Projects are always written locally first (`./<name>/`), followed by optional `git init` and `graphify update .` hooks, and optional GitHub repo creation/push (`-r github --create`).

**Tech Stack:** Python 3.11+ (`tomllib`, `string.Template`, `pathlib`, `subprocess`, `shutil`), `typer>=0.9`, `PyGithub>=2.0`, `pytest>=8`.

**Spec:** `docs/superpowers/specs/2026-10-17-ai-agent-bootstrapper-design.md`

## Global Constraints

- Requires Python `>=3.11`; use stdlib `tomllib` for parsing `presets.toml` (zero new runtime dependencies in `pyproject.toml`).
- All template rendering MUST use `bootstrapper.templates.render` (`string.Template.safe_substitute`) so `{{ .Values.x }}` and `${{ secrets.X }}` pass through untouched.
- User config directory MUST respect `PROJBOOT_HOME` environment variable and default to `~/.config/projboot`.
- All local file writes MUST pass through `_safe_join` to prevent path traversal.
- Offline/local commands and `pytest` suite MUST NOT require `GITHUB_TOKEN` or network access.

---

### Task 1: Presets & User Store Module (`bootstrapper/presets.py`)

**Files:**
- Create: `bootstrapper/presets.py`
- Test: `tests/test_presets.py`

**Interfaces:**
- Consumes: `pathlib.Path`, `tomllib`
- Produces:
  - `PresetConfig` (dataclass with `name: str`, `arch: str`, `outputs_dir: str`, `scripts_dir: str`, `prompts_file: str`, `agents: list[str]`)
  - `BUILTIN_PRESETS: dict[str, PresetConfig]`
  - `get_config_dir() -> Path`
  - `load_presets(config_dir: Path | None = None) -> dict[str, PresetConfig]`
  - `resolve_preset(preset_name: str, *, arch: str | None = None, outputs_dir: str | None = None, scripts_dir: str | None = None, prompts_file: str | None = None, agents: list[str] | None = None, config_dir: Path | None = None) -> PresetConfig`
  - `load_user_store_files(config_dir: Path | None = None) -> dict[str, str]`
  - `init_config_dir(config_dir: Path | None = None, *, force: bool = False) -> list[Path]`

- [ ] **Step 1: Write the failing tests in `tests/test_presets.py`**

```python
from pathlib import Path
import pytest

from bootstrapper.presets import (
    PresetConfig,
    get_config_dir,
    init_config_dir,
    load_presets,
    load_user_store_files,
    resolve_preset,
)


def test_get_config_dir_uses_env(monkeypatch, tmp_path):
    custom = tmp_path / "custom_projboot"
    monkeypatch.setenv("PROJBOOT_HOME", str(custom))
    assert get_config_dir() == custom


def test_builtin_presets_loaded_when_no_config_file(tmp_path):
    presets = load_presets(tmp_path)
    assert "default" in presets
    assert "clean-arch" in presets
    default = presets["default"]
    assert default.arch == "modular"
    assert default.outputs_dir == "outputs"
    assert default.scripts_dir == "scripts"
    assert default.prompts_file == "PROMPTS.md"


def test_user_presets_toml_overrides_and_adds(tmp_path):
    (tmp_path / "presets.toml").write_text(
        '[presets.default]\n'
        'outputs_dir = "custom-out"\n\n'
        '[presets.go-hex]\n'
        'arch = "hexagonal"\n'
        'outputs_dir = "dist/out"\n'
        'scripts_dir = "hack"\n'
        'prompts_file = "docs/prompts.md"\n'
        'agents = ["claude", "gh-copilot"]\n'
    )
    presets = load_presets(tmp_path)
    assert presets["default"].outputs_dir == "custom-out"
    assert presets["default"].scripts_dir == "scripts"
    hex_p = presets["go-hex"]
    assert hex_p == PresetConfig(
        name="go-hex",
        arch="hexagonal",
        outputs_dir="dist/out",
        scripts_dir="hack",
        prompts_file="docs/prompts.md",
        agents=["claude", "gh-copilot"],
    )


def test_resolve_preset_cli_overrides_win(tmp_path):
    resolved = resolve_preset(
        "default",
        arch="event-driven",
        outputs_dir="build/out",
        scripts_dir="bin",
        prompts_file="AI_PROMPTS.md",
        agents=["claude"],
        config_dir=tmp_path,
    )
    assert resolved.arch == "event-driven"
    assert resolved.outputs_dir == "build/out"
    assert resolved.scripts_dir == "bin"
    assert resolved.prompts_file == "AI_PROMPTS.md"
    assert resolved.agents == ["claude"]


def test_resolve_preset_unknown_raises_key_error(tmp_path):
    with pytest.raises(KeyError, match="Unknown preset 'nonexistent'"):
        resolve_preset("nonexistent", config_dir=tmp_path)


def test_init_config_dir_and_load_user_store(tmp_path):
    created = init_config_dir(tmp_path)
    assert (tmp_path / "presets.toml").exists()
    assert len(created) >= 4

    # Add a custom skill and custom remember note in the user store
    custom_skill = tmp_path / "skills" / "my-skill" / "SKILL.md"
    custom_skill.parent.mkdir(parents=True, exist_ok=True)
    custom_skill.write_text("# Skill for $name\nOutputs in $outputs_dir\n")

    files = load_user_store_files(tmp_path)
    assert ".agents/skills/my-skill/SKILL.md" in files
    assert "$outputs_dir" in files[".agents/skills/my-skill/SKILL.md"]
    assert ".remember/MEMORY.md" in files
    assert ".remember/decisions.md" in files
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_presets.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bootstrapper.presets'`

- [ ] **Step 3: Write implementation in `bootstrapper/presets.py`**

```python
"""Preset management and ~/.config/projboot/ user store loader."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class PresetConfig:
    name: str
    arch: str = "modular"
    outputs_dir: str = "outputs"
    scripts_dir: str = "scripts"
    prompts_file: str = "PROMPTS.md"
    agents: list[str] = field(default_factory=list)


BUILTIN_PRESETS: dict[str, PresetConfig] = {
    "default": PresetConfig(
        name="default",
        arch="modular",
        outputs_dir="outputs",
        scripts_dir="scripts",
        prompts_file="PROMPTS.md",
        agents=[],
    ),
    "clean-arch": PresetConfig(
        name="clean-arch",
        arch="clean-architecture",
        outputs_dir="artifacts/outputs",
        scripts_dir="scripts",
        prompts_file="docs/PROMPTS.md",
        agents=["claude", "gh-copilot"],
    ),
}

DEFAULT_PRESETS_TOML = """\
# projboot workflow presets
# Customize folders, architecture style, and default AI agents per preset.

[presets.default]
arch = "modular"
outputs_dir = "outputs"
scripts_dir = "scripts"
prompts_file = "PROMPTS.md"
agents = []

[presets.clean-arch]
arch = "clean-architecture"
outputs_dir = "artifacts/outputs"
scripts_dir = "scripts"
prompts_file = "docs/PROMPTS.md"
agents = ["claude", "gh-copilot"]
"""

DEFAULT_REMEMBER_FILES: dict[str, str] = {
    "MEMORY.md": (
        "# Project Memory ($name)\n\n"
        "Persistent context and facts for AI agents working in `$name`.\n\n"
        "## Key Conventions\n"
        "- Architecture: `$arch`\n"
        "- Generated outputs directory: `$outputs_dir/`\n"
        "- Helper scripts directory: `$scripts_dir/`\n"
        "- Ordered prompts file: `$prompts_file`\n"
    ),
    "decisions.md": (
        "# Architectural & Product Decisions ($name)\n\n"
        "Log key technical decisions chronologically so agents preserve context across sessions.\n\n"
        "## $year — Initial Bootstrap\n"
        "- Bootstrapped `$name` with `$arch` architecture.\n"
    ),
}

DEFAULT_SKILL_FILES: dict[str, str] = {
    "project-conventions/SKILL.md": (
        "---\n"
        "name: project-conventions\n"
        "description: Core workspace layout, output directories, and prompt tracking rules for $name.\n"
        "---\n\n"
        "# Project Conventions for `$name`\n\n"
        "1. **Architecture**: Follow the `$arch` architecture pattern.\n"
        "2. **Outputs**: Write generated artifacts, reports, and exports to `$outputs_dir/`.\n"
        "3. **Scripts**: Save reusable automation and helper scripts in `$scripts_dir/`.\n"
        "4. **Prompts**: Keep reusable and ordered prompts documented in `$prompts_file`.\n"
        "5. **Memory**: Read and update `.remember/MEMORY.md` and `.remember/decisions.md`.\n"
        "6. **Knowledge Graph**: Use `graphify-out/` and run `graphify update .` after code edits.\n"
    ),
}


def get_config_dir() -> Path:
    env_dir = os.environ.get("PROJBOOT_HOME")
    if env_dir:
        return Path(env_dir).expanduser()
    return Path.home() / ".config" / "projboot"


def load_presets(config_dir: Path | None = None) -> dict[str, PresetConfig]:
    root = config_dir if config_dir is not None else get_config_dir()
    presets: dict[str, PresetConfig] = dict(BUILTIN_PRESETS)

    toml_path = root / "presets.toml"
    if not toml_path.is_file():
        return presets

    data = tomllib.loads(toml_path.read_text())
    raw_presets = data.get("presets", {})
    if not isinstance(raw_presets, dict):
        return presets

    for name, cfg in raw_presets.items():
        if not isinstance(cfg, dict):
            continue
        base = presets.get(name, PresetConfig(name=name))
        presets[name] = PresetConfig(
            name=name,
            arch=str(cfg.get("arch", base.arch)),
            outputs_dir=str(cfg.get("outputs_dir", base.outputs_dir)),
            scripts_dir=str(cfg.get("scripts_dir", base.scripts_dir)),
            prompts_file=str(cfg.get("prompts_file", base.prompts_file)),
            agents=[str(a) for a in cfg.get("agents", base.agents)],
        )
    return presets


def resolve_preset(
    preset_name: str = "default",
    *,
    arch: str | None = None,
    outputs_dir: str | None = None,
    scripts_dir: str | None = None,
    prompts_file: str | None = None,
    agents: list[str] | None = None,
    config_dir: Path | None = None,
) -> PresetConfig:
    presets = load_presets(config_dir)
    if preset_name not in presets:
        available = ", ".join(sorted(presets))
        raise KeyError(f"Unknown preset '{preset_name}'. Available: {available}")
    base = presets[preset_name]

    merged_agents: list[str] = list(base.agents)
    for a in agents or []:
        if a not in merged_agents:
            merged_agents.append(a)

    return PresetConfig(
        name=base.name,
        arch=arch if arch is not None else base.arch,
        outputs_dir=(outputs_dir if outputs_dir is not None else base.outputs_dir).rstrip("/"),
        scripts_dir=(scripts_dir if scripts_dir is not None else base.scripts_dir).rstrip("/"),
        prompts_file=prompts_file if prompts_file is not None else base.prompts_file,
        agents=merged_agents,
    )


def _collect_dir_files(directory: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not directory.is_dir():
        return out
    for path in sorted(directory.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            rel = path.relative_to(directory).as_posix()
            out[rel] = path.read_text()
    return out


def load_user_store_files(config_dir: Path | None = None) -> dict[str, str]:
    """Load `.remember/` and `.agents/skills/` templates from user store or built-in defaults."""
    root = config_dir if config_dir is not None else get_config_dir()
    files: dict[str, str] = {}

    user_remember = _collect_dir_files(root / "remember")
    remember_source = user_remember if user_remember else DEFAULT_REMEMBER_FILES
    for rel, content in remember_source.items():
        files[f".remember/{rel}"] = content

    user_skills = _collect_dir_files(root / "skills")
    skills_source = user_skills if user_skills else DEFAULT_SKILL_FILES
    for rel, content in skills_source.items():
        files[f".agents/skills/{rel}"] = content

    return files


def init_config_dir(config_dir: Path | None = None, *, force: bool = False) -> list[Path]:
    """Materialize default presets.toml, skills/, and remember/ into the user config dir."""
    root = config_dir if config_dir is not None else get_config_dir()
    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    targets: list[tuple[Path, str]] = [
        (root / "presets.toml", DEFAULT_PRESETS_TOML),
        *[
            (root / "remember" / rel, body)
            for rel, body in DEFAULT_REMEMBER_FILES.items()
        ],
        *[
            (root / "skills" / rel, body)
            for rel, body in DEFAULT_SKILL_FILES.items()
        ],
    ]
    for path, content in targets:
        if path.exists() and not force:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        written.append(path)
    return written
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_presets.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add bootstrapper/presets.py tests/test_presets.py
git commit -m "feat(presets): add preset resolution and ~/.config/projboot user store loader"
```

---

### Task 2: Universal Agent Harness & Assistant Adapters (`bootstrapper/agents.py`)

**Files:**
- Create: `bootstrapper/agents.py`
- Test: `tests/test_agents.py`

**Interfaces:**
- Consumes: `bootstrapper.presets.PresetConfig`, `bootstrapper.presets.load_user_store_files`
- Produces:
  - `SUPPORTED_AGENTS: tuple[str, ...] = ("claude", "gh-copilot", "codeassistant", "cursor")`
  - `universal_harness_files(preset: PresetConfig, config_dir: Path | None = None) -> dict[str, str]`
  - `agent_overlay_files(agents: list[str]) -> dict[str, str]`

- [ ] **Step 1: Write the failing tests in `tests/test_agents.py`**

```python
import pytest

from bootstrapper.agents import (
    SUPPORTED_AGENTS,
    agent_overlay_files,
    universal_harness_files,
)
from bootstrapper.presets import PresetConfig
from bootstrapper.templates import render


def test_universal_harness_includes_graphify_remember_skills_and_custom_paths(tmp_path):
    preset = PresetConfig(
        name="custom",
        arch="hexagonal",
        outputs_dir="out/artifacts",
        scripts_dir="hack/scripts",
        prompts_file="docs/PROMPTS.md",
    )
    raw_files = universal_harness_files(preset, config_dir=tmp_path)
    assert "AGENTS.md" in raw_files
    assert "graphify-out/.gitkeep" in raw_files
    assert "out/artifacts/.gitkeep" in raw_files
    assert "hack/scripts/.gitkeep" in raw_files
    assert "docs/PROMPTS.md" in raw_files
    assert ".remember/MEMORY.md" in raw_files
    assert ".agents/skills/project-conventions/SKILL.md" in raw_files

    rendered_agents = render(
        raw_files["AGENTS.md"],
        name="demo-ai",
        description="AI service",
        arch=preset.arch,
        outputs_dir=preset.outputs_dir,
        scripts_dir=preset.scripts_dir,
        prompts_file=preset.prompts_file,
    )
    assert "hexagonal" in rendered_agents
    assert "out/artifacts/" in rendered_agents
    assert "hack/scripts/" in rendered_agents
    assert "docs/PROMPTS.md" in rendered_agents
    assert "graphify-out/" in rendered_agents


def test_agent_overlays_for_claude_and_copilot():
    overlays = agent_overlay_files(["claude", "gh-copilot"])
    assert "CLAUDE.md" in overlays
    assert ".claude/settings.json" in overlays
    assert ".github/copilot-instructions.md" in overlays
    assert ".github/prompts/bootstrap.prompt.md" in overlays


def test_agent_overlays_for_codeassistant_and_cursor():
    overlays = agent_overlay_files(["codeassistant", "cursor"])
    assert ".codeassistant/instructions.md" in overlays
    assert ".cursor/rules/project.mdc" in overlays


def test_unknown_agent_raises_key_error():
    with pytest.raises(KeyError, match="Unknown agent 'unknown-bot'"):
        agent_overlay_files(["unknown-bot"])


def test_supported_agents_constant():
    assert set(SUPPORTED_AGENTS) == {"claude", "gh-copilot", "codeassistant", "cursor"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_agents.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bootstrapper.agents'`

- [ ] **Step 3: Write implementation in `bootstrapper/agents.py`**

```python
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
        ".claude/settings.json": (
            "{\n"
            '  "project": "$name",\n'
            '  "conventions": {\n'
            '    "outputsDir": "$outputs_dir",\n'
            '    "scriptsDir": "$scripts_dir",\n'
            '    "promptsFile": "$prompts_file"\n'
            "  }\n"
            "}\n"
        ),
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
            "description: Core project architecture and directory rules for $name\n"
            "globs: *\n"
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_agents.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add bootstrapper/agents.py tests/test_agents.py
git commit -m "feat(agents): add universal agent harness and assistant overlays"
```

---

### Task 3: Layered Composer & Post-Scaffold Hooks (`bootstrapper/composer.py` & `bootstrapper/templates.py`)

**Files:**
- Modify: `bootstrapper/templates.py`
- Create: `bootstrapper/composer.py`
- Test: `tests/test_composer.py`

**Interfaces:**
- Consumes: `bootstrapper.templates`, `bootstrapper.presets`, `bootstrapper.agents`
- Produces:
  - In `bootstrapper/templates.py`: aliases `"python"` -> `"python-microservice"` and adds `"none"` template (minimal `README.md` + `.gitignore`) via `resolve_template(lang_or_template: str) -> dict`
  - In `bootstrapper/composer.py`:
    - `compose_project_files(*, name: str, description: str, lang: str, preset: PresetConfig, license: str = "none", holder: str = "", extra_vars: dict[str, str] | None = None, config_dir: Path | None = None) -> dict[str, str]`
    - `run_post_hooks(target: Path, *, init_git: bool = True, run_graphify: bool = True) -> list[str]`

- [ ] **Step 1: Write the failing tests in `tests/test_composer.py`**

```python
from pathlib import Path
from unittest.mock import patch

from bootstrapper.composer import compose_project_files, run_post_hooks
from bootstrapper.presets import resolve_preset


def test_compose_python_with_claude_and_copilot(tmp_path):
    preset = resolve_preset(
        "default",
        arch="clean-arch",
        outputs_dir="out",
        scripts_dir="hack",
        prompts_file="PROMPTS.md",
        agents=["claude", "gh-copilot"],
        config_dir=tmp_path,
    )
    files = compose_project_files(
        name="my-agent-app",
        description="Agentic service",
        lang="python",
        preset=preset,
        license="mit",
        holder="Alice",
        config_dir=tmp_path,
    )
    # Base python template files
    assert "pyproject.toml" in files
    assert 'name = "my-agent-app"' in files["pyproject.toml"]
    assert "src/main.py" in files

    # Universal harness files
    assert "AGENTS.md" in files
    assert "out/" in files["AGENTS.md"]
    assert "hack/" in files["AGENTS.md"]
    assert "graphify-out/.gitkeep" in files
    assert "out/.gitkeep" in files
    assert "hack/.gitkeep" in files
    assert "PROMPTS.md" in files
    assert ".remember/MEMORY.md" in files
    assert ".agents/skills/project-conventions/SKILL.md" in files

    # Agent overlays
    assert "CLAUDE.md" in files
    assert ".github/copilot-instructions.md" in files
    assert "LICENSE" in files
    assert "Alice" in files["LICENSE"]


def test_run_post_hooks_invokes_git_and_graphify(tmp_path):
    calls: list[list[str]] = []

    def fake_run(cmd, cwd, check, capture_output, text):
        calls.append(cmd)

    with (
        patch("bootstrapper.composer.shutil.which", return_value="/usr/local/bin/graphify"),
        patch("bootstrapper.composer.subprocess.run", side_effect=fake_run),
    ):
        messages = run_post_hooks(tmp_path, init_git=True, run_graphify=True)

    assert ["git", "init", "-b", "main"] in calls
    assert ["/usr/local/bin/graphify", "update", "."] in calls
    assert len(messages) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_composer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bootstrapper.composer'`

- [ ] **Step 3: Update `bootstrapper/templates.py` and create `bootstrapper/composer.py`**

In `bootstrapper/templates.py`, add `"none"` to `TEMPLATES` and add `TEMPLATE_ALIASES = {"python": "python-microservice"}` in `get_template`:

```python
TEMPLATE_ALIASES: dict[str, str] = {
    "python": "python-microservice",
}
```
And in `TEMPLATES`:
```python
    "none": {
        "name": "none",
        "description": "Minimal agent-only repository (README and .gitignore only)",
        "files": {
            "README.md": "# $name\n\n$description\n",
            ".gitignore": ".env\n.venv/\n__pycache__/\n*.py[cod]\n",
        },
    },
```
And in `get_template(name: str) -> dict`:
```python
def get_template(name: str) -> dict:
    resolved = TEMPLATE_ALIASES.get(name, name)
    if resolved not in TEMPLATES:
        raise KeyError(
            f"Unknown template '{name}'. Available: {', '.join(template_names())}"
        )
    return TEMPLATES[resolved]
```

Create `bootstrapper/composer.py`:

```python
"""Layered file composition pipeline and post-scaffold hooks."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import shutil
import subprocess

from .agents import agent_overlay_files, universal_harness_files
from .presets import PresetConfig
from .templates import LICENSES, get_template, render

DEFAULT_GRAPHIFY_BIN = Path("/Users/mac/.local/bin/graphify")


def compose_project_files(
    *,
    name: str,
    description: str,
    lang: str,
    preset: PresetConfig,
    license: str = "none",
    holder: str = "",
    extra_vars: dict[str, str] | None = None,
    config_dir: Path | None = None,
) -> dict[str, str]:
    """Compose and render all files for an AI-enabled project scaffold."""
    variables: dict[str, str] = {
        "name": name,
        "description": description or f"{name} project",
        "year": str(dt.date.today().year),
        "holder": holder or name,
        "arch": preset.arch,
        "outputs_dir": preset.outputs_dir,
        "scripts_dir": preset.scripts_dir,
        "prompts_file": preset.prompts_file,
    }
    if extra_vars:
        variables.update(extra_vars)

    raw_files: dict[str, str] = {}
    spec = get_template(lang)
    raw_files.update(spec["files"])
    raw_files.update(universal_harness_files(preset, config_dir=config_dir))
    raw_files.update(agent_overlay_files(preset.agents))

    if license != "none":
        lic_body = LICENSES.get(license)
        if lic_body is not None:
            raw_files["LICENSE"] = lic_body

    return {
        render(path, **variables): render(body, **variables)
        for path, body in raw_files.items()
    }


def _find_graphify() -> str | None:
    which_bin = shutil.which("graphify")
    if which_bin:
        return which_bin
    if DEFAULT_GRAPHIFY_BIN.is_file():
        return str(DEFAULT_GRAPHIFY_BIN)
    return None


def run_post_hooks(
    target: Path,
    *,
    init_git: bool = True,
    run_graphify: bool = True,
) -> list[str]:
    """Run best-effort local post-scaffold hooks (git init, graphify update)."""
    messages: list[str] = []

    if init_git:
        try:
            subprocess.run(
                ["git", "init", "-b", "main"],
                cwd=target,
                check=True,
                capture_output=True,
                text=True,
            )
            messages.append("Initialized git repository (main)")
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            messages.append(f"Skipped git init: {exc}")

    if run_graphify:
        graphify_bin = _find_graphify()
        if graphify_bin:
            try:
                subprocess.run(
                    [graphify_bin, "update", "."],
                    cwd=target,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                messages.append("Initialized graphify knowledge graph (graphify-out/)")
            except (FileNotFoundError, subprocess.CalledProcessError) as exc:
                messages.append(f"Skipped graphify update: {exc}")
        else:
            messages.append("Skipped graphify update (graphify binary not found)")

    return messages
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_composer.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add bootstrapper/templates.py bootstrapper/composer.py tests/test_composer.py
git commit -m "feat(composer): add layered project composer and git/graphify post-hooks"
```

---

### Task 4: CLI Commands (`projboot create`, `config-init`, `list-presets`), Entrypoint & Docs

**Files:**
- Modify: `pyproject.toml`
- Modify: `bootstrapper/cli.py`
- Modify: `tests/test_cli.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `bootstrapper.presets`, `bootstrapper.agents`, `bootstrapper.composer`
- Produces:
  - `projboot` console script entrypoint in `pyproject.toml`
  - `create`, `config-init`, and `list-presets` commands on `bootstrapper.cli:app`
  - Updated `README.md` covering `projboot create`, presets, `~/.config/projboot/`, and agent overlays

- [ ] **Step 1: Add failing CLI tests in `tests/test_cli.py`**

Append to `tests/test_cli.py`:

```python
def test_create_ai_project_local_with_agents_and_custom_dirs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJBOOT_HOME", str(tmp_path / "projboot_home"))
    res = _run(
        [
            "create",
            "new-project",
            "-l",
            "python",
            "-a",
            "claude",
            "-a",
            "gh-copilot",
            "--outputs-dir",
            "custom-outputs",
            "--scripts-dir",
            "custom-scripts",
            "--prompts-file",
            "MY_PROMPTS.md",
            "--no-git",
            "--no-graphify",
        ]
    )
    assert res.exit_code == 0, res.stdout
    proj = tmp_path / "new-project"
    assert (proj / "AGENTS.md").exists()
    assert (proj / "CLAUDE.md").exists()
    assert (proj / ".github" / "copilot-instructions.md").exists()
    assert (proj / "graphify-out" / ".gitkeep").exists()
    assert (proj / ".remember" / "MEMORY.md").exists()
    assert (proj / ".agents" / "skills" / "project-conventions" / "SKILL.md").exists()
    assert (proj / "custom-outputs" / ".gitkeep").exists()
    assert (proj / "custom-scripts" / ".gitkeep").exists()
    assert (proj / "MY_PROMPTS.md").exists()
    assert "custom-outputs/" in (proj / "CLAUDE.md").read_text()
    assert "custom-scripts/" in (proj / ".github" / "copilot-instructions.md").read_text()


def test_create_ai_project_with_github_remote(tmp_path, monkeypatch):
    import bootstrapper.github_utils as gu

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJBOOT_HOME", str(tmp_path / "projboot_home"))

    calls: list[tuple[str, str]] = []
    fake_repo = MagicMock()
    fake_repo.clone_url = "https://github.com/acme/new-project.git"

    monkeypatch.setattr(gu, "get_github", lambda: MagicMock())
    monkeypatch.setattr(gu, "get_owner", lambda gh, org: MagicMock())
    monkeypatch.setattr(gu, "create_repo", lambda owner, n, d, p: fake_repo)
    monkeypatch.setattr(
        gu, "add_file", lambda repo, path, content, message: calls.append((path, content))
    )

    res = _run(
        [
            "create",
            "new-project",
            "-l",
            "python",
            "-a",
            "claude",
            "-a",
            "gh-copilot",
            "-r",
            "github",
            "--create",
            "--clone",
            "--no-git",
            "--no-graphify",
        ]
    )
    assert res.exit_code == 0, res.stdout
    # Local directory is created AND remote files are pushed
    assert (tmp_path / "new-project" / "CLAUDE.md").exists()
    pushed = {p for p, _ in calls}
    assert "AGENTS.md" in pushed
    assert "CLAUDE.md" in pushed
    assert ".github/copilot-instructions.md" in pushed


def test_config_init_and_list_presets(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "projboot_cfg"
    monkeypatch.setenv("PROJBOOT_HOME", str(cfg_dir))

    res_init = _run(["config-init"])
    assert res_init.exit_code == 0, res_init.stdout
    assert (cfg_dir / "presets.toml").exists()

    res_list = _run(["list-presets"])
    assert res_list.exit_code == 0, res_list.stdout
    assert "default" in res_list.stdout
    assert "clean-arch" in res_list.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: FAIL with `No such command 'create'`

- [ ] **Step 3: Update `pyproject.toml`, `bootstrapper/cli.py`, and `README.md`**

In `pyproject.toml`:
```toml
[project.scripts]
project-bootstrapper = "bootstrapper.cli:app"
projboot = "bootstrapper.cli:app"
```

In `bootstrapper/cli.py`, add `list-presets`, `config-init`, and `create` commands wiring `resolve_preset`, `compose_project_files`, `_write_local`, `run_post_hooks`, and optional `_emit` to GitHub when `-r github --create` is set.

Update `README.md` with full documentation for `projboot create`, presets (`~/.config/projboot/`), universal agent harness, `-a` assistant flags, and custom layout parameters.

- [ ] **Step 4: Run entire test suite to verify all tests pass**

Run: `.venv/bin/pytest -v`
Expected: PASS (all tests green)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml bootstrapper/cli.py tests/test_cli.py README.md docs/superpowers/plans/2026-10-17-ai-agent-bootstrapper.md
git commit -m "feat(cli): add projboot create, presets, agent overlays, and documentation"
```
