"""D1: `preview` shows exactly what `create` would write/run, with no side effects."""

import pytest
from typer.testing import CliRunner

import bootstrapper.cli as cli_mod
import bootstrapper.composer as composer_mod
import bootstrapper.github_utils as gu
from bootstrapper.cli import app

runner = CliRunner()


def _run(args):
    return runner.invoke(app, args)


def _section_lines(stdout: str, header_prefix: str) -> list[str]:
    """Indented entries of the first section whose header starts with the prefix."""
    lines = stdout.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith(header_prefix)),
        None,
    )
    assert start is not None, f"section {header_prefix!r} missing from:\n{stdout}"
    out: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("  "):
            out.append(line[2:])
        else:
            break
    return out


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJBOOT_HOME", str(tmp_path / "projboot_home"))
    monkeypatch.chdir(tmp_path)


VARIANTS = {
    "basic": ["pv-basic", "-l", "python", "--no-git", "--no-graphify"],
    "full": [
        "pv-full", "-l", "python", "-a", "claude", "-a", "gh-copilot",
        "--preset", "clean-arch", "--outputs-dir", "custom-outputs",
        "--scripts-dir", "custom-scripts", "--prompts-file", "MY_PROMPTS.md",
        "--license", "mit", "--holder", "ACME", "--no-git", "--no-graphify",
    ],
    "bare": ["pv-bare", "-l", "none", "--no-git", "--no-graphify"],
}


def _created_files(root):
    return {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.parts
    }


@pytest.mark.parametrize("args", list(VARIANTS.values()), ids=list(VARIANTS))
def test_preview_paths_match_create_for_identical_arguments(tmp_path, args):
    res = _run(["preview", *args])
    assert res.exit_code == 0, res.stdout
    previewed = set(_section_lines(res.stdout, "Files that `create` would write"))

    created = _run(["create", *args])
    assert created.exit_code == 0, created.stdout
    assert previewed == _created_files(tmp_path / args[0])


def test_preview_reports_directory_layout(tmp_path):
    res = _run(["preview", "pv", "-l", "python", "--no-git", "--no-graphify"])
    assert res.exit_code == 0, res.stdout
    dirs = _section_lines(res.stdout, "Directories implied by that layout")
    assert "src/" in dirs


def test_preview_writes_nothing_including_no_staging_dir(tmp_path):
    res = _run(["preview", "demo", "-l", "python"])
    assert res.exit_code == 0, res.stdout
    assert list(tmp_path.iterdir()) == []


def test_preview_never_runs_hooks_pushes_or_subprocesses(monkeypatch):
    hook_calls: list = []
    push_calls: list = []
    github_calls: list = []

    monkeypatch.setattr(
        cli_mod, "run_post_hooks",
        lambda *a, **k: hook_calls.append(a) or [],
    )
    monkeypatch.setattr(
        cli_mod, "_push_github",
        lambda *a, **k: push_calls.append(a) or "https://x",
    )
    monkeypatch.setattr(gu, "get_github", lambda: github_calls.append("gh") or None)
    monkeypatch.setattr(
        composer_mod, "subprocess",
        type("Boom", (), {"run": lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("preview must not spawn subprocesses")
        )}),
    )

    res = _run([
        "preview", "demo", "-l", "python",
        "--create", "--clone", "-r", "github",
    ])
    assert res.exit_code == 0, res.stdout
    assert hook_calls == []
    assert push_calls == []
    assert github_calls == []


INVALID_OR_COLLIDING = {
    "bad-name": [["not a name"], "bad name rejected before any write"],
    "bad-var": [["pv", "--var", "noequals"], "malformed --var rejected"],
    "clone-without-create": [["pv", "--clone"], "--clone requires --create"],
    "clone-with-no-git": [["pv", "--clone", "--no-git"], "contradictory flags"],
    "bad-remote": [["pv", "-r", "gitlab"], "unsupported remote"],
    "escaping-outputs-dir": [["pv", "--outputs-dir", "../escape"], "path escape"],
    "colliding-prompts-file": [["pv", "--prompts-file", "src/main.py"], "collision"],
    "unknown-preset": [["pv", "--preset", "nope"], "unknown preset"],
    "unknown-agent": [["pv", "-a", "nope"], "unknown agent"],
}


@pytest.mark.parametrize(
    "args,reason",
    [(v[0], v[1]) for v in INVALID_OR_COLLIDING.values()],
    ids=list(INVALID_OR_COLLIDING),
)
def test_preview_fails_invalid_inputs_before_any_side_effect(tmp_path, args, reason):
    res = _run(["preview", *args])
    assert res.exit_code != 0, f"{reason}: preview accepted bad input:\n{res.stdout}"
    assert list(tmp_path.iterdir()) == [], f"{reason}: preview left files behind"


def test_preview_refuses_nonempty_target_and_leaves_it_untouched(tmp_path):
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "keep.txt").write_text("precious")
    res = _run(["preview", "demo", "-l", "python", "--no-git", "--no-graphify"])
    assert res.exit_code != 0
    assert (tmp_path / "demo" / "keep.txt").read_text() == "precious"
    assert set(p.name for p in tmp_path.iterdir()) == {"demo"}


def test_preview_distinguishes_selected_required_and_not_executed(tmp_path):
    res = _run(["preview", "demo", "-l", "python", "-a", "claude", "--create", "-r", "github"])
    assert res.exit_code == 0, res.stdout
    out = res.stdout
    actions = "\n".join(_section_lines(out, "Post-generation actions"))
    assert "git init" in actions
    assert "not executed" in actions
    assert "create GitHub repository" in actions
    assert "graphify" in actions
    # A selected requirement is never reported as satisfied.
    for line in actions.splitlines():
        if "graphify" in line or "GitHub" in line:
            assert "NOT CHECKED" in line

    selected = _section_lines(out, "Selected tools and integrations")
    assert any(line.startswith("agents: claude") for line in selected)


def test_preview_reports_requested_github_organization(tmp_path):
    res = _run([
        "preview", "demo", "-l", "python", "--create", "-r", "github",
        "--org", "example-org", "--no-git", "--no-graphify",
    ])
    assert res.exit_code == 0, res.stdout
    actions = _section_lines(res.stdout, "Post-generation actions")
    assert "GitHub organization (--org): example-org" in actions


def test_preview_marks_deselected_actions(tmp_path):
    res = _run(["preview", "demo", "-l", "python", "--no-git", "--no-graphify"])
    assert res.exit_code == 0, res.stdout
    actions = "\n".join(_section_lines(res.stdout, "Post-generation actions"))
    assert "not selected (--no-git)" in actions
    assert "not selected (--no-graphify)" in actions
    assert "not selected" in actions and "create GitHub repository" in actions
