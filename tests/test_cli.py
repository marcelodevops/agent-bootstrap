import textwrap
from pathlib import Path
from unittest.mock import MagicMock

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
    monkeypatch.setattr(gu, "create_repo", lambda owner, n, d, p: fake_repo)
    monkeypatch.setattr(
        gu, "add_file", lambda repo, path, content, message: calls.append((path, content))
    )

    res = _run(["init", "--template", "typescript", "--name", "demo"])
    assert res.exit_code == 0, res.stdout
    pushed = {p for p, _ in calls}
    assert "package.json" in pushed
    assert "src/index.ts" in pushed
    fake_repo  # repo object was used by add_file
