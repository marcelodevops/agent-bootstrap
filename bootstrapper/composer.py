"""Layered file composition pipeline and post-scaffold hooks."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile

from .agents import agent_overlay_files, universal_harness_files
from .presets import PresetConfig
from .templates import LICENSES, get_template, render

DEFAULT_GRAPHIFY_BIN = Path("~/.local/bin/graphify")


class PathCollisionError(ValueError):
    """Two composition layers produce the same path with different content."""


def find_output_conflicts(files: dict[str, str]) -> None:
    """Raise ``PathCollisionError`` if the plan would silently lose content.

    Detects two conflicts that the raw-key merge cannot see because they only
    appear once paths are rendered/normalized:

    * **Same destination via alias** — e.g. ``README.md`` and ``./README.md``
      normalize to one path but carry different content, so one would overwrite
      the other. Identical content under an alias is allowed (nothing is lost).
    * **File over directory** — e.g. a rendered file ``src`` alongside
      ``src/main.py``; ``src`` must be a directory to hold the latter, so writing
      either order crashes halfway and leaves a partial project.

    Ancestors that are only ever directories (``.github`` in
    ``.github/workflows/ci.yml``) are not files here, so valid plans pass.
    """
    owners: dict[str, tuple[str, str]] = {}  # normalized path -> (original, content)
    for rel, content in files.items():
        norm = PurePosixPath(rel).as_posix()
        prev = owners.get(norm)
        if prev is not None and prev[1] != content:
            raise PathCollisionError(
                f"'{prev[0]}' and '{rel}' resolve to the same output '{norm}' "
                "with different content; adjust --prompts-file/--outputs-dir/"
                "--scripts-dir or the agent set so nothing is overwritten"
            )
        owners[norm] = (rel, content)

    destinations = set(owners)
    for norm, (rel, _content) in owners.items():
        for ancestor in PurePosixPath(norm).parents:
            apos = ancestor.as_posix()
            if apos in destinations and apos != norm:
                other = owners[apos][0]
                raise PathCollisionError(
                    f"'{other}' is generated as a file but is also the parent "
                    f"directory of '{rel}'; refusing to create a conflicting path"
                )


def _merge(dst: dict[str, str], src: dict[str, str], layer: str) -> None:
    """Merge ``src`` into ``dst``, refusing silent overwrites of differing files."""
    for key, value in src.items():
        if key in dst and dst[key] != value:
            raise PathCollisionError(
                f"path '{key}' is produced by the '{layer}' layer but already "
                "exists with different content; adjust --prompts-file/"
                "--outputs-dir/--scripts-dir or the agent set to avoid the clash"
            )
        dst[key] = value


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
    include_graphify: bool = True,
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

    harness = universal_harness_files(
        preset,
        config_dir=config_dir,
        lang=lang,
        include_graphify=include_graphify,
    )
    remember_files = sorted(p for p in harness if p.startswith(".remember/"))
    skill_files = sorted(p for p in harness if p.startswith(".agents/skills/"))

    raw_files: dict[str, str] = {}
    _merge(raw_files, get_template(lang)["files"], "base template")
    _merge(raw_files, harness, "agent harness")
    _merge(
        raw_files,
        agent_overlay_files(
            preset.agents,
            include_graphify=include_graphify,
            remember_files=remember_files,
            skill_files=skill_files,
        ),
        "assistant overlays",
    )

    if license != "none":
        lic_body = LICENSES.get(license)
        if lic_body is not None:
            _merge(raw_files, {"LICENSE": lic_body}, "license")

    rendered: dict[str, str] = {}
    for path, body in raw_files.items():
        rendered_path = render(path, **variables)
        rendered_body = render(body, **variables)
        # Two different raw paths may render to the same destination; refuse to
        # let a dict literal silently keep only the last one's content.
        if (
            rendered_path in rendered
            and rendered[rendered_path] != rendered_body
        ):
            raise PathCollisionError(
                f"rendered path '{rendered_path}' is produced twice with "
                "different content; refusing to overwrite"
            )
        rendered[rendered_path] = rendered_body
    find_output_conflicts(rendered)
    return rendered


def _find_graphify() -> str | None:
    which_bin = shutil.which("graphify")
    if which_bin:
        return which_bin
    candidate = (
        Path.home() / ".local" / "bin" / "graphify"
        if DEFAULT_GRAPHIFY_BIN == Path("~/.local/bin/graphify")
        else DEFAULT_GRAPHIFY_BIN.expanduser()
    )
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


def run_post_hooks(
    target: Path,
    *,
    init_git: bool = True,
    run_graphify: bool = True,
    connect_remote_url: str | None = None,
    make_commit: bool = False,
    stage_paths: list[str] | None = None,
) -> list[str]:
    """Run best-effort local post-scaffold hooks (git init/remote/commit, graphify)."""
    messages: list[str] = []

    if init_git:
        initialized = False
        try:
            subprocess.run(
                ["git", "init", "-b", "main"],
                cwd=target,
                check=True,
                capture_output=True,
                text=True,
            )
            messages.append("Initialized git repository (main)")
            initialized = True
        except (OSError, subprocess.CalledProcessError) as exc:
            messages.append(f"Skipped git init: {exc}")

        remote_added = False
        if connect_remote_url and initialized:
            if _git_ok(target, ["git", "remote", "add", "origin", connect_remote_url]):
                messages.append(f"Added origin remote: {connect_remote_url}")
                remote_added = True
            elif _git_ok(target, ["git", "remote", "set-url", "origin", connect_remote_url]):
                messages.append(f"Updated origin remote: {connect_remote_url}")
                remote_added = True
            else:
                messages.append(f"Skipped origin remote setup: git could not set {connect_remote_url}")

        if make_commit and initialized and remote_added:
            index_env = None
            if stage_paths is None:
                staged = _git_ok(target, ["git", "add", "-A"])
            else:
                index_dir = tempfile.TemporaryDirectory(prefix="projboot-index-")
                index_env = {
                    **os.environ,
                    "GIT_INDEX_FILE": str(Path(index_dir.name) / "index"),
                }
                base_tree = (
                    ["git", "read-tree", "HEAD"]
                    if _git_ok(target, ["git", "rev-parse", "--verify", "HEAD"])
                    else ["git", "read-tree", "--empty"]
                )
                staged = _git_ok(target, base_tree, env=index_env) and _git_ok(
                    target, ["git", "add", "--", *stage_paths], env=index_env
                )
            if not staged:
                messages.append("Skipped initial commit: git add failed")
            elif _git_ok(
                target,
                [
                    "git",
                    "-c", "user.name=projboot",
                    "-c", "user.email=projboot@localhost",
                    "commit",
                    "-m", "Bootstrap project scaffold",
                ],
                env=index_env,
            ):
                messages.append("Created initial commit")
                if stage_paths is not None and not _git_ok(
                    target, ["git", "reset", "-q", "HEAD", "--", *stage_paths]
                ):
                    messages.append(
                        "Warning: local index could not be synchronized with the initial commit"
                    )
                if _git_ok(target, ["git", "push", "--set-upstream", "origin", "main"]):
                    messages.append("Pushed initial commit to origin (main)")
                else:
                    messages.append("Skipped initial push: git push failed; remote history was not rewritten")
            else:
                messages.append("Skipped initial commit: git commit failed")
            if stage_paths is not None:
                index_dir.cleanup()

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
            except (OSError, subprocess.CalledProcessError) as exc:
                messages.append(f"Skipped graphify update: {exc}")
        else:
            messages.append("Skipped graphify update (graphify binary not found)")

    return messages


def _git_ok(cwd: Path, cmd: list[str], *, env: dict[str, str] | None = None) -> bool:
    """Run a best-effort git command; True on success, False otherwise."""
    try:
        kwargs = {"cwd": cwd, "check": True, "capture_output": True, "text": True}
        if env is not None:
            kwargs["env"] = env
        subprocess.run(cmd, **kwargs)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False
