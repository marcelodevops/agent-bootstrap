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
