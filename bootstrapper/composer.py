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
