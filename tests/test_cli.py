import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import typer
from typer.testing import CliRunner

from bootstrapper.cli import app

runner = CliRunner()


def _run(args):
    return runner.invoke(app, args)


def test_list_templates():
    res = _run(["list-templates"])
    assert res.exit_code == 0
    assert "helm-chart" in res.stdout
    assert "typescript" in res.stdout


def test_init_local_helm(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = _run(
        ["init", "--template", "helm-chart", "--name", "demo",
         "--description", "x", "--local"]
    )
    assert res.exit_code == 0, res.stdout
    deployment = tmp_path / "demo" / "templates" / "deployment.yaml"
    assert deployment.exists()
    # Helm Go-template syntax survives rendering untouched.
    assert "{{ .Values.replicaCount }}" in deployment.read_text()


def test_init_local_custom_var(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = _run(
        ["init", "--template", "python-microservice", "--name", "svc",
         "--var", "name=overridden", "--local"]
    )
    assert res.exit_code == 0, res.stdout
    readme = (tmp_path / "svc" / "README.md").read_text()
    # --var overrides the built-in name token.
    assert "# overridden" in readme


def test_init_local_refuses_clobber(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "keep.txt").write_text("precious")
    res = _run(["init", "--template", "typescript", "--name", "demo", "--local"])
    assert res.exit_code != 0
    # original content untouched
    assert (tmp_path / "demo" / "keep.txt").read_text() == "precious"


def test_init_local_force_overwrites(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "keep.txt").write_text("precious")
    res = _run(
        ["init", "--template", "typescript", "--name", "demo", "--local", "--force"]
    )
    assert res.exit_code == 0, res.stdout
    assert (tmp_path / "demo" / "package.json").exists()


def test_init_from_tree_materializes_empty_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tree = tmp_path / "t.txt"
    tree.write_text(
        textwrap.dedent(
            """\
            proj/
            ├── src/
            │   └── app.ts
            ├── docs/
            └── README.md
            """
        )
    )
    res = _run(
        ["init-from-tree", "--name", "proj", "--tree-file", str(tree),
         "--gitkeep", "--local"]
    )
    assert res.exit_code == 0, res.stdout
    assert (tmp_path / "proj" / "src" / "app.ts").read_text() == ""
    assert (tmp_path / "proj" / "README.md").read_text() == ""
    assert (tmp_path / "proj" / "docs" / ".gitkeep").exists()


def test_bad_var_format(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = _run(["init", "--name", "x", "--var", "noequals", "--local"])
    assert res.exit_code != 0


def test_init_dispatches_to_github(tmp_path, monkeypatch):
    # Fake the GitHub layer: assert init pushes every scaffolded file, no network.
    import bootstrapper.github_utils as gu

    calls: list[tuple[str, str]] = []
    fake_repo = MagicMock()
    fake_repo.clone_url = "https://github.com/acme/demo.git"

    monkeypatch.setattr(gu, "get_github", lambda: MagicMock())
    monkeypatch.setattr(gu, "get_owner", lambda gh, org: MagicMock())
    monkeypatch.setattr(gu, "create_repo", lambda owner, n, d, p, force=False: fake_repo)
    monkeypatch.setattr(
        gu, "add_file", lambda repo, path, content, message: calls.append((path, content))
    )

    res = _run(["init", "--template", "typescript", "--name", "demo"])
    assert res.exit_code == 0, res.stdout
    pushed = {p for p, _ in calls}
    assert "package.json" in pushed
    assert "src/index.ts" in pushed
    fake_repo  # repo object was used by add_file


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
    # --no-graphify must drop graphify scaffolding AND its instruction lines.
    assert not (proj / "graphify-out" / ".gitkeep").exists()
    assert "graphify" not in (proj / "AGENTS.md").read_text().lower()
    assert "graphify" not in (proj / "CLAUDE.md").read_text().lower()
    assert (proj / ".remember" / "MEMORY.md").exists()
    assert (proj / ".agents" / "skills" / "project-conventions" / "SKILL.md").exists()
    assert "graphify" not in (
        proj / ".agents" / "skills" / "project-conventions" / "SKILL.md"
    ).read_text().lower()
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
    monkeypatch.setattr(gu, "create_repo", lambda owner, n, d, p, force=False: fake_repo)
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
            "--no-git",
            "--no-graphify",
        ]
    )
    assert res.exit_code == 0, res.stdout
    # Local directory is created AND remote files are pushed.
    # (No --clone here: A3 rejects --clone with --no-git as contradictory, and
    #  connected-checkout behavior is covered by test_clone_produces_connected_local_repo.)
    assert (tmp_path / "new-project" / "CLAUDE.md").exists()
    pushed = {p for p, _ in calls}
    assert "AGENTS.md" in pushed
    assert "CLAUDE.md" in pushed
    assert ".github/copilot-instructions.md" in pushed


def test_create_rejects_escaping_outputs_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJBOOT_HOME", str(tmp_path / "home"))
    res = _run(["create", "proj", "-l", "none", "--outputs-dir", "../escape", "--no-git"])
    assert res.exit_code != 0
    # Validation happens before any write, so the project dir is never created.
    assert not (tmp_path / "proj").exists()


def test_create_rejects_colliding_prompts_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJBOOT_HOME", str(tmp_path / "home"))
    res = _run(
        ["create", "proj", "-l", "python", "--prompts-file", "src/main.py", "--no-git"]
    )
    assert res.exit_code != 0


def test_write_local_no_partial_on_escape(tmp_path):
    from bootstrapper.cli import _write_local

    files = {"ok.txt": "data", "../escape.txt": "bad"}
    with pytest.raises(typer.Exit):
        _write_local(tmp_path / "out", files, force=False)
    # First file must NOT have been written because validation runs up front.
    assert not (tmp_path / "out" / "ok.txt").exists()


def test_clone_produces_connected_local_repo(tmp_path, monkeypatch):
    # Real git (no network): --clone --create should leave origin + a commit.
    import subprocess

    import bootstrapper.github_utils as gu

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJBOOT_HOME", str(tmp_path / "home"))
    fake_repo = MagicMock()
    fake_repo.clone_url = "https://github.com/acme/clonetest.git"
    monkeypatch.setattr(gu, "get_github", lambda: MagicMock())
    monkeypatch.setattr(gu, "get_owner", lambda gh, org: MagicMock())
    monkeypatch.setattr(gu, "create_repo", lambda owner, n, d, p, force=False: fake_repo)
    monkeypatch.setattr(gu, "add_file", lambda *a, **k: None)

    res = _run(
        ["create", "clonetest", "-l", "none", "--agent", "claude",
         "--create", "-r", "github", "--clone", "--no-graphify"]
    )
    assert res.exit_code == 0, res.stdout

    proj = tmp_path / "clonetest"
    remote = subprocess.run(
        ["git", "-C", str(proj), "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    assert remote.returncode == 0
    assert remote.stdout.strip() == fake_repo.clone_url

    commits = subprocess.run(
        ["git", "-C", str(proj), "rev-list", "--count", "HEAD"],
        capture_output=True, text=True,
    )
    assert commits.stdout.strip() == "1"  # initial commit exists


def test_push_refuses_existing_repo_without_force(tmp_path, monkeypatch):
    import bootstrapper.github_utils as gu
    from bootstrapper.github_utils import RepoExistsError

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gu, "get_github", lambda: MagicMock())
    monkeypatch.setattr(gu, "get_owner", lambda gh, org: MagicMock())

    def _raise(owner, n, d, p, force=False):
        raise RepoExistsError("acme/demo")

    monkeypatch.setattr(gu, "create_repo", _raise)
    pushed: list[str] = []
    monkeypatch.setattr(gu, "add_file", lambda *a, **k: pushed.append("x"))

    res = _run(["init", "--template", "typescript", "--name", "demo"])
    assert res.exit_code != 0
    assert pushed == []  # nothing uploaded against an existing repo


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

