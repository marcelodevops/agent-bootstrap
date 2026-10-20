"""Preset management and ~/.config/projboot/ user store loader."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path, PurePosixPath
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

def _build_default_project_conventions_skill(
    *,
    include_graphify: bool = True,
    remember_files: list[str] | None = None,
) -> str:
    if remember_files:
        mem_refs = " and ".join(f"`{p}`" for p in remember_files)
    else:
        mem_refs = "`.remember/MEMORY.md` and `.remember/decisions.md`"
    base = (
        "---\n"
        "name: project-conventions\n"
        "description: Core workspace layout, output directories, and prompt tracking rules for $name.\n"
        "---\n\n"
        "# Project Conventions for `$name`\n\n"
        "1. **Architecture**: Follow the `$arch` architecture pattern.\n"
        "2. **Outputs**: Write generated artifacts, reports, and exports to `$outputs_dir/`.\n"
        "3. **Scripts**: Save reusable automation and helper scripts in `$scripts_dir/`.\n"
        "4. **Prompts**: Keep reusable and ordered prompts documented in `$prompts_file`.\n"
        f"5. **Memory**: Read and update {mem_refs}.\n"
    )
    if include_graphify:
        return (
            base
            + "6. **Knowledge Graph**: When `graphify-out/graph.json` is populated and the external "
            "`graphify` CLI is available, query `graphify-out/` and run `graphify update .` after code edits.\n"
        )
    return base


_LEGACY_DEFAULT_SKILL_BODY = (
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
)

DEFAULT_SKILL_FILES: dict[str, str] = {
    "project-conventions/SKILL.md": _build_default_project_conventions_skill(
        include_graphify=True
    ),
}

_UNEDITED_DEFAULT_SKILL_BODIES: frozenset[str] = frozenset(
    {
        _LEGACY_DEFAULT_SKILL_BODY,
        DEFAULT_SKILL_FILES["project-conventions/SKILL.md"],
        _build_default_project_conventions_skill(include_graphify=False),
    }
)

_SHAREABLE_ENV_SUFFIXES: tuple[str, ...] = (".example", ".sample", ".template")
_SHAREABLE_ENV_STEMS: tuple[str, ...] = ("example", "sample", "template")


def _is_shareable_env_template(filename: str) -> bool:
    """Return True if ``filename`` is a shareable env example/sample/template."""
    lower = filename.lower()
    if lower in {".env.example", ".env.sample", ".env.template"}:
        return True
    if lower.startswith(".env.") and lower.endswith(_SHAREABLE_ENV_SUFFIXES):
        return True
    if lower.endswith(".env"):
        stem = lower[: -len(".env")]
        if stem in _SHAREABLE_ENV_STEMS or stem.endswith(
            tuple(f".{s}" for s in _SHAREABLE_ENV_STEMS)
        ):
            return True
    return False


def _is_forbidden_env_or_hidden(rel: PurePosixPath) -> bool:
    """Return True if a user-store path is a secret `.env` variant or hidden entry."""
    parts = rel.parts
    if not parts:
        return True
    if any(part.startswith(".") for part in parts[:-1]):
        return True
    name = parts[-1]
    lower = name.lower()
    if _is_shareable_env_template(name):
        return False
    if lower == ".env" or lower.startswith(".env.") or lower.endswith(".env"):
        return True
    if name.startswith("."):
        return True
    return False


def validate_rel_path(value: str, field: str) -> str:
    """Ensure a preset path is a safe, repo-relative POSIX path.

    Rejects absolute paths, ``~`` home expansion, and any ``..`` traversal so a
    custom --outputs-dir/--scripts-dir/--prompts-file cannot escape the project
    root or overwrite files outside it.
    """
    raw = value.strip()
    if not raw:
        raise ValueError(f"{field} must not be empty")
    if "\x00" in raw:
        raise ValueError(f"{field} contains a null byte")
    norm = raw.replace("\\", "/")
    if norm.startswith("/") or norm.startswith("~"):
        raise ValueError(f"{field} must be relative to the project root: {value!r}")
    parts = PurePosixPath(norm).parts
    if ".." in parts:
        raise ValueError(f"{field} must not contain '..': {value!r}")
    return norm


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
        outputs_dir=validate_rel_path(
            (outputs_dir if outputs_dir is not None else base.outputs_dir).rstrip("/"),
            "--outputs-dir",
        ),
        scripts_dir=validate_rel_path(
            (scripts_dir if scripts_dir is not None else base.scripts_dir).rstrip("/"),
            "--scripts-dir",
        ),
        prompts_file=validate_rel_path(
            prompts_file if prompts_file is not None else base.prompts_file,
            "--prompts-file",
        ),
        agents=merged_agents,
    )


def _has_symlink_component(root: Path, target: Path) -> bool:
    """Return True if ``root`` or any segment from ``root`` to ``target`` is a symlink."""
    if root.is_symlink():
        return True
    cur = target
    while cur != root:
        if cur.is_symlink():
            return True
        if cur.parent == cur:
            break
        cur = cur.parent
    return False


def _collect_dir_files(directory: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not directory.is_dir() or directory.is_symlink():
        return out
    resolved_root = directory.resolve()
    for path in sorted(directory.rglob("*")):
        if _has_symlink_component(directory, path) or not path.is_file():
            continue
        rel_posix = PurePosixPath(path.relative_to(directory).as_posix())
        if _is_forbidden_env_or_hidden(rel_posix):
            continue
        try:
            resolved_path = path.resolve(strict=True)
            resolved_rel = PurePosixPath(
                resolved_path.relative_to(resolved_root).as_posix()
            )
        except (OSError, ValueError):
            continue
        if not resolved_path.is_file() or _is_forbidden_env_or_hidden(resolved_rel):
            continue
        out[rel_posix.as_posix()] = resolved_path.read_text()
    return out


def load_user_store_files(
    config_dir: Path | None = None,
    *,
    include_graphify: bool = True,
) -> dict[str, str]:
    """Load `.remember/` and `.agents/skills/` templates from user store merged over defaults."""
    root = config_dir if config_dir is not None else get_config_dir()
    files: dict[str, str] = {}

    user_remember = _collect_dir_files(root / "remember")
    remember_source = {**DEFAULT_REMEMBER_FILES, **user_remember}
    for rel, content in remember_source.items():
        files[f".remember/{rel}"] = content

    default_skill_body = _build_default_project_conventions_skill(
        include_graphify=include_graphify
    )
    user_skills = _collect_dir_files(root / "skills")
    skills_source = {"project-conventions/SKILL.md": default_skill_body, **user_skills}
    if (
        "project-conventions/SKILL.md" in user_skills
        and user_skills["project-conventions/SKILL.md"] in _UNEDITED_DEFAULT_SKILL_BODIES
    ):
        skills_source["project-conventions/SKILL.md"] = default_skill_body
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
