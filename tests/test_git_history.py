import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

import bootstrapper.cli as cli
import bootstrapper.composer as composer
import bootstrapper.github_utils as github_utils


runner = CliRunner()


def _git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *(str(arg) for arg in args)],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_clone_pushes_one_generated_history_and_excludes_unrelated_files(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJBOOT_HOME", str(tmp_path / "home"))
    remote = tmp_path / "remote.git"
    _git("init", "--bare", "--initial-branch=main", str(remote))
    repo = MagicMock(clone_url=str(remote))
    monkeypatch.setattr(github_utils, "get_github", lambda: MagicMock())
    monkeypatch.setattr(github_utils, "get_owner", lambda gh, org: MagicMock())
    monkeypatch.setattr(
        github_utils, "create_repo", lambda owner, n, d, p, force=False: repo
    )

    write_local = cli._write_local

    def write_with_unrelated_file(target, files, force):
        write_local(target, files, force)
        (target / "unrelated.txt").write_text("must stay untracked\n")

    git_ok = composer._git_ok
    staged_unrelated = False

    def stage_unrelated_before_bootstrap_commit(cwd, command, **kwargs):
        nonlocal staged_unrelated
        if command[:3] == ["git", "remote", "add"] and not staged_unrelated:
            _git("add", "unrelated.txt", cwd=cwd)
            staged_unrelated = True
        return git_ok(cwd, command, **kwargs)

    monkeypatch.setattr(cli, "_write_local", write_with_unrelated_file)
    monkeypatch.setattr(composer, "_git_ok", stage_unrelated_before_bootstrap_commit)
    result = runner.invoke(
        cli.app,
        [
            "create", "history-demo", "-l", "none", "--create", "--clone",
            "-r", "github", "--no-graphify",
        ],
    )
    assert result.exit_code == 0, result.stdout
    local = tmp_path / "history-demo"
    local_head = _git("rev-parse", "HEAD", cwd=local)
    remote_head = _git("rev-parse", "refs/heads/main", cwd=remote)
    assert local_head == remote_head
    assert _git("rev-list", "--count", "HEAD", cwd=local) == "1"
    assert "AGENTS.md" in _git("ls-tree", "--name-only", "HEAD", cwd=local)
    assert "unrelated.txt" not in _git("ls-tree", "--name-only", "HEAD", cwd=local)
    assert _git("diff", "--cached", "--name-only", cwd=local) == "unrelated.txt"
    assert "Pushed initial commit to origin (main)" in result.stdout
    assert "GitHub remote: ran" in result.stdout


def test_clone_push_failure_is_reported_as_partial_without_ready_claim(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJBOOT_HOME", str(tmp_path / "home"))
    missing_remote = tmp_path / "missing.git"
    repo = MagicMock(clone_url=str(missing_remote))
    monkeypatch.setattr(github_utils, "get_github", lambda: MagicMock())
    monkeypatch.setattr(github_utils, "get_owner", lambda gh, org: MagicMock())
    monkeypatch.setattr(
        github_utils, "create_repo", lambda owner, n, d, p, force=False: repo
    )

    result = runner.invoke(
        cli.app,
        [
            "create", "partial-demo", "-l", "none", "--create", "--clone",
            "-r", "github", "--no-graphify",
        ],
    )
    assert result.exit_code == 1, result.stdout
    assert "Skipped initial push: git push failed" in result.stdout
    assert "GitHub remote: partial / pending" in result.stdout
    assert "local git remote/commit/push: pending / incomplete" in result.stdout
    assert "GitHub remote: ran" not in result.stdout
    assert "Repo ready:" not in result.stdout


def test_force_clone_preserves_existing_tracked_tree_and_staged_changes(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJBOOT_HOME", str(tmp_path / "home"))
    target = tmp_path / "existing-demo"
    target.mkdir()
    (target / "existing.txt").write_text("keep in project history\n")
    _git("init", "-b", "main", cwd=target)
    _git("-c", "user.name=prior", "-c", "user.email=prior@localhost", "add", "existing.txt", cwd=target)
    _git("-c", "user.name=prior", "-c", "user.email=prior@localhost", "commit", "-m", "prior project", cwd=target)
    (target / "unrelated.txt").write_text("keep staged, do not push\n")
    _git("add", "unrelated.txt", cwd=target)

    remote = tmp_path / "existing-remote.git"
    _git("init", "--bare", "--initial-branch=main", str(remote))
    repo = MagicMock(clone_url=str(remote))
    monkeypatch.setattr(github_utils, "get_github", lambda: MagicMock())
    monkeypatch.setattr(github_utils, "get_owner", lambda gh, org: MagicMock())
    monkeypatch.setattr(
        github_utils, "create_repo", lambda owner, n, d, p, force=False: repo
    )

    result = runner.invoke(
        cli.app,
        [
            "create", "existing-demo", "-l", "none", "--force", "--create",
            "--clone", "-r", "github", "--no-graphify",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert _git("rev-parse", "HEAD", cwd=target) == _git(
        "rev-parse", "refs/heads/main", cwd=remote
    )
    tree_paths = _git("ls-tree", "--name-only", "HEAD", cwd=target).splitlines()
    assert "existing.txt" in tree_paths
    assert "AGENTS.md" in tree_paths
    assert "unrelated.txt" not in tree_paths
    assert _git("diff", "--cached", "--name-only", cwd=target) == "unrelated.txt"
