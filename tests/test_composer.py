from unittest.mock import patch

import pytest

from bootstrapper.composer import (
    PathCollisionError,
    compose_project_files,
    run_post_hooks,
)
from bootstrapper.presets import resolve_preset


def test_compose_rejects_prompts_file_colliding_with_template(tmp_path):
    # --prompts-file src/main.py would silently clobber the python entrypoint.
    preset = resolve_preset("default", prompts_file="src/main.py", agents=[])
    with pytest.raises(PathCollisionError, match="src/main.py"):
        compose_project_files(
            name="p",
            description="d",
            lang="python",
            preset=preset,
            config_dir=tmp_path,
        )


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


def test_run_post_hooks_connects_remote_and_commits(tmp_path):
    calls: list[list[str]] = []

    def fake_run(cmd, cwd, check, capture_output, text):
        calls.append(cmd)

    with patch("bootstrapper.composer.subprocess.run", side_effect=fake_run):
        messages = run_post_hooks(
            tmp_path,
            init_git=True,
            run_graphify=False,
            connect_remote_url="https://github.com/acme/demo.git",
            make_commit=True,
        )

    assert ["git", "remote", "add", "origin", "https://github.com/acme/demo.git"] in calls
    assert ["git", "add", "-A"] in calls
    assert any(c[:1] == ["git"] and "commit" in c for c in calls)
    assert any("origin" in m for m in messages)
    assert "Created initial commit" in messages


def test_run_post_hooks_skips_remote_when_no_git(tmp_path):
    calls: list[list[str]] = []

    def fake_run(cmd, cwd, check, capture_output, text):
        calls.append(cmd)

    with patch("bootstrapper.composer.subprocess.run", side_effect=fake_run):
        # init_git=False must not run ANY git command (no init, remote, commit).
        run_post_hooks(
            tmp_path,
            init_git=False,
            run_graphify=False,
            connect_remote_url="https://x/y.git",
            make_commit=True,
        )

    assert calls == []
