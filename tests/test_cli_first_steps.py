"""D2 behavioral tests: `create` prints accurate, profile-derived first steps,
user-runnable checks, actual hook outcomes, and explicit unverified boundaries.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import bootstrapper.cli as cli_mod
import bootstrapper.composer as composer_mod
from bootstrapper.cli import app

runner = CliRunner()


def _run(args: list[str]):
    return runner.invoke(app, args)


def _section_lines(stdout: str, header_prefix: str) -> list[str]:
    """Return indented lines under the first section header starting with `header_prefix`."""
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
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PROJBOOT_HOME", str(tmp_path / "projboot_home"))
    monkeypatch.chdir(tmp_path)


@pytest.mark.parametrize("lang", ["python", "python-microservice"])
def test_create_python_first_steps_and_user_run_checks_derive_from_scaffold(
    tmp_path: Path, lang: str
):
    name = f"py-svc-{lang}"
    res = _run(
        [
            "create",
            name,
            "-l",
            lang,
            "-a",
            "claude",
            "--outputs-dir",
            "artifacts/out",
            "--scripts-dir",
            "hack/bin",
            "--prompts-file",
            "docs/PROMPTS.md",
            "--no-git",
            "--no-graphify",
        ]
    )
    assert res.exit_code == 0, res.stdout
    out = res.stdout

    generated = "\n".join(_section_lines(out, f"Generated and configured in {name}/"))
    assert lang in generated
    assert "src/appstarter/" in generated
    assert "AGENTS.md" in generated
    assert "docs/PROMPTS.md" in generated
    assert "artifacts/out/" in generated
    assert "hack/bin/" in generated
    assert "claude" in generated
    assert "CLAUDE.md" in generated
    assert "not verified" in generated.lower()
    assert "graphify-out/" not in generated or "not selected" in generated.lower()

    steps = _section_lines(out, "First steps (user-run commands — not executed")
    steps_text = "\n".join(steps)
    assert f"cd {name}" in steps_text
    assert "pip install -e ." in steps_text
    assert "appstarter" in steps_text
    assert "python -m appstarter" in steps_text
    for line in steps:
        assert "[not executed]" in line, f"First-step line missing [not executed]: {line!r}"

    checks = _section_lines(out, "User-runnable verification checks (not executed")
    checks_text = "\n".join(checks)
    assert "pytest" in checks_text
    assert "python -m build" in checks_text
    for line in checks:
        assert "[not executed]" in line, f"Check line missing [not executed]: {line!r}"

    lowered = out.lower()
    for foreign in ("npm ", "tsc", "helm ", "ruby -c", "bundle install", "rails "):
        assert foreign not in lowered, f"Foreign command {foreign!r} leaked into Python output"
    assert "graphify update ." not in steps_text.lower()


def test_create_typescript_first_steps_and_checks_without_invented_test_runner(
    tmp_path: Path,
):
    res = _run(
        [
            "create",
            "ts-svc",
            "-l",
            "typescript",
            "-a",
            "gh-copilot",
            "-a",
            "cursor",
            "--no-git",
            "--no-graphify",
        ]
    )
    assert res.exit_code == 0, res.stdout
    out = res.stdout

    generated = "\n".join(_section_lines(out, "Generated and configured in ts-svc/"))
    assert "typescript" in generated
    assert "gh-copilot" in generated
    assert "cursor" in generated

    steps = _section_lines(out, "First steps (user-run commands — not executed")
    steps_text = "\n".join(steps)
    assert "cd ts-svc" in steps_text
    assert "npm install" in steps_text
    assert "npm run build" in steps_text
    assert "npm start" in steps_text
    for line in steps:
        assert "[not executed]" in line

    checks = _section_lines(out, "User-runnable verification checks (not executed")
    checks_text = "\n".join(checks)
    assert "npm run build" in checks_text
    assert "no test script" in checks_text.lower() or "no test runner" in checks_text.lower()
    assert "npm test" not in checks_text.lower()
    for line in checks:
        assert "[not executed]" in line

    lowered = out.lower()
    for foreign in ("pytest", "pip install", "appstarter", "helm ", "ruby -c", "rails "):
        assert foreign not in lowered


def test_create_helm_chart_first_steps_and_checks_without_claiming_cluster_deploy(
    tmp_path: Path,
):
    res = _run(
        [
            "create",
            "billing-chart",
            "-l",
            "helm-chart",
            "--no-git",
            "--no-graphify",
        ]
    )
    assert res.exit_code == 0, res.stdout
    out = res.stdout

    steps = _section_lines(out, "First steps (user-run commands — not executed")
    steps_text = "\n".join(steps)
    assert "cd billing-chart" in steps_text
    assert "values.yaml" in steps_text
    for line in steps:
        assert "[not executed]" in line

    checks = _section_lines(out, "User-runnable verification checks (not executed")
    checks_text = "\n".join(checks)
    assert "helm lint ." in checks_text
    assert "helm template billing-chart ." in checks_text
    for line in checks:
        assert "[not executed]" in line

    unverified = "\n".join(_section_lines(out, "Unverified / pending items"))
    assert "cluster" in unverified.lower() or "deployment" in unverified.lower()

    lowered = out.lower()
    for foreign in ("pytest", "pip install", "appstarter", "npm ", "tsc", "ruby -c", "rails "):
        assert foreign not in lowered


def test_create_rails_keeps_experimental_label_and_syntax_only_check(tmp_path: Path):
    res = _run(
        [
            "create",
            "rails-sketch",
            "-l",
            "rails",
            "--no-git",
            "--no-graphify",
        ]
    )
    assert res.exit_code == 0, res.stdout
    out = res.stdout

    generated = "\n".join(_section_lines(out, "Generated and configured in rails-sketch/"))
    assert "experimental" in generated.lower()
    assert "not a runnable rails app" in generated.lower()

    steps = _section_lines(out, "First steps (user-run commands — not executed")
    steps_text = "\n".join(steps)
    assert "experimental" in steps_text.lower()
    assert "rails new" in steps_text
    assert "rails server" not in steps_text.lower()
    for line in steps:
        assert "[not executed]" in line

    checks = _section_lines(out, "User-runnable verification checks (not executed")
    checks_text = "\n".join(checks)
    assert (
        "ruby -c config/application.rb && ruby -c app/controllers/application_controller.rb"
        in checks_text
    )
    assert "syntax" in checks_text.lower()
    assert "unavailable" in checks_text.lower()
    for line in checks:
        assert "[not executed]" in line

    unverified = "\n".join(_section_lines(out, "Unverified / pending items"))
    assert "experimental" in unverified.lower()

    lowered = out.lower()
    for foreign in ("pytest", "pip install", "appstarter", "npm ", "tsc", "helm "):
        assert foreign not in lowered


def test_create_none_profile_invents_no_language_commands_or_checks(tmp_path: Path):
    res = _run(
        [
            "create",
            "bare-agent",
            "-l",
            "none",
            "-a",
            "codeassistant",
            "--prompts-file",
            "NOTES.md",
            "--no-git",
            "--no-graphify",
        ]
    )
    assert res.exit_code == 0, res.stdout
    out = res.stdout

    generated = "\n".join(_section_lines(out, "Generated and configured in bare-agent/"))
    assert "none" in generated
    assert "NOTES.md" in generated
    assert "codeassistant" in generated

    steps = _section_lines(out, "First steps (user-run commands — not executed")
    steps_text = "\n".join(steps)
    assert "cd bare-agent" in steps_text
    assert "AGENTS.md" in steps_text
    assert "NOTES.md" in steps_text
    for line in steps:
        assert "[not executed]" in line

    checks = _section_lines(out, "User-runnable verification checks (not executed")
    checks_text = "\n".join(checks)
    assert "no language" in checks_text.lower()
    for line in checks:
        assert "[not executed]" in line

    lowered = out.lower()
    for foreign in (
        "pytest",
        "pip install",
        "appstarter",
        "npm ",
        "tsc",
        "helm ",
        "ruby -c",
        "bundle ",
        "rails ",
    ):
        assert foreign not in lowered


def test_create_hook_outcomes_reflect_actual_results_never_false_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Case 1: Both git and graphify are skipped due to missing/failing tools
    monkeypatch.setattr(
        cli_mod,
        "run_post_hooks",
        lambda *a, **k: [
            "Skipped git init: [Errno 2] No such file or directory: 'git'",
            "Skipped graphify update (graphify binary not found)",
        ],
    )
    res_skipped = _run(["create", "skipped-hooks", "-l", "python"])
    assert res_skipped.exit_code == 0, res_skipped.stdout
    hooks_skipped = "\n".join(
        _section_lines(res_skipped.stdout, "Hook & remote status (actual results)")
    )
    assert "git init: pending / not run" in hooks_skipped
    assert "graphify update .: pending / not run" in hooks_skipped
    assert "git init: ran" not in hooks_skipped
    assert "graphify update .: ran" not in hooks_skipped

    # When graphify was requested but skipped, first steps offer `graphify update .` as [not executed]
    steps_skipped = "\n".join(
        _section_lines(res_skipped.stdout, "First steps (user-run commands — not executed")
    )
    assert "graphify update ." in steps_skipped
    unverified_skipped = "\n".join(
        _section_lines(res_skipped.stdout, "Unverified / pending items")
    )
    assert "graphify" in unverified_skipped.lower()
    assert "placeholder" in unverified_skipped.lower()

    # Case 2: Both git and graphify actually run and succeed
    monkeypatch.setattr(
        cli_mod,
        "run_post_hooks",
        lambda *a, **k: [
            "Initialized git repository (main)",
            "Initialized graphify knowledge graph (graphify-out/)",
        ],
    )
    res_ran = _run(["create", "ran-hooks", "-l", "python"])
    assert res_ran.exit_code == 0, res_ran.stdout
    hooks_ran = "\n".join(
        _section_lines(res_ran.stdout, "Hook & remote status (actual results)")
    )
    assert "git init: ran — Initialized git repository (main)" in hooks_ran
    assert (
        "graphify update .: ran — Initialized graphify knowledge graph (graphify-out/)"
        in hooks_ran
    )
    assert "dependencies, build, and tests: not run" in hooks_ran


def test_create_never_claims_dependencies_build_tests_clients_or_github_verified_when_not_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    res = _run(
        [
            "create",
            "honest-app",
            "-l",
            "python",
            "-a",
            "claude",
            "-a",
            "cursor",
            "-r",
            "github",
            "--no-git",
            "--no-graphify",
        ]
    )
    assert res.exit_code == 0, res.stdout
    hooks = "\n".join(_section_lines(res.stdout, "Hook & remote status (actual results)"))
    assert "git init: not run (--no-git)" in hooks
    assert "graphify update .: not selected (--no-graphify)" in hooks
    assert "GitHub remote: not run" in hooks
    assert "dependencies, build, and tests: not run" in hooks

    unverified = "\n".join(_section_lines(res.stdout, "Unverified / pending items"))
    assert "dependencies" in unverified.lower()
    assert "assistant overlays (claude, cursor)" in unverified
    assert "not verified" in unverified.lower()
    assert "github" in unverified.lower()

    # Now with --create (mocked): GitHub creation is reported, but dependencies/build/tests/clients stay unverified
    import bootstrapper.github_utils as gu

    fake_repo = MagicMock()
    fake_repo.clone_url = "https://github.com/acme/honest-remote.git"
    monkeypatch.setattr(gu, "get_github", lambda: MagicMock())
    monkeypatch.setattr(gu, "get_owner", lambda gh, org: MagicMock())
    monkeypatch.setattr(gu, "create_repo", lambda owner, n, d, p, force=False: fake_repo)
    monkeypatch.setattr(gu, "add_file", lambda *a, **k: None)

    res_remote = _run(
        [
            "create",
            "honest-remote",
            "-l",
            "python",
            "-a",
            "claude",
            "-r",
            "github",
            "--create",
            "--no-git",
            "--no-graphify",
        ]
    )
    assert res_remote.exit_code == 0, res_remote.stdout
    hooks_remote = "\n".join(
        _section_lines(res_remote.stdout, "Hook & remote status (actual results)")
    )
    assert "https://github.com/acme/honest-remote.git" in hooks_remote
    assert "dependencies, build, and tests: not run" in hooks_remote
    unverified_remote = "\n".join(
        _section_lines(res_remote.stdout, "Unverified / pending items")
    )
    assert "dependencies" in unverified_remote.lower()
    assert "assistant overlays (claude)" in unverified_remote


def test_create_summary_never_spawns_generated_project_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        composer_mod,
        "subprocess",
        type(
            "Boom",
            (),
            {
                "run": lambda *a, **k: (_ for _ in ()).throw(
                    AssertionError("create with --no-git --no-graphify must not spawn subprocesses")
                )
            },
        ),
    )
    res = _run(["create", "offline-only", "-l", "python", "--no-git", "--no-graphify"])
    assert res.exit_code == 0, res.stdout


def test_create_native_hooks_report_missing_binaries_as_pending_never_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Real `run_post_hooks` execution (no mock) with empty PATH and empty HOME
    must report both `git init` and `graphify update .` as pending / not run.
    """
    empty_home = tmp_path / "empty_home"
    empty_home.mkdir()
    monkeypatch.setenv("HOME", str(empty_home))
    monkeypatch.setenv("PATH", "")

    res = _run(["create", "native-no-tools", "-l", "python"])
    assert res.exit_code == 0, res.stdout
    hooks = "\n".join(
        _section_lines(res.stdout, "Hook & remote status (actual results)")
    )
    assert "git init: pending / not run" in hooks
    assert "graphify update .: pending / not run" in hooks
    assert "git init: ran" not in hooks
    assert "graphify update .: ran" not in hooks

    unverified = "\n".join(_section_lines(res.stdout, "Unverified / pending items"))
    assert "git repository: pending / not initialized" in unverified
    assert "graphify knowledge graph: pending / not built" in unverified


def test_create_derives_checks_from_actual_composed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """If the composed file plan omits `tests/test_appstarter.py`, `create` must
    not instruct the user to run `pytest` against a nonexistent test suite.
    """
    orig_compose = cli_mod.compose_project_files

    def compose_without_tests(**kwargs):
        files = orig_compose(**kwargs)
        files.pop("tests/test_appstarter.py", None)
        return files

    monkeypatch.setattr(cli_mod, "compose_project_files", compose_without_tests)
    res = _run(["create", "no-tests-py", "-l", "python", "--no-git", "--no-graphify"])
    assert res.exit_code == 0, res.stdout

    checks = "\n".join(
        _section_lines(res.stdout, "User-runnable verification checks (not executed")
    )
    assert "pytest" not in checks
    assert "python -m build" in checks


def test_create_clone_reports_push_failure_and_partial_wiring_when_git_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import bootstrapper.github_utils as gu

    fake_repo = MagicMock()
    fake_repo.clone_url = "https://github.com/acme/clone-svc.git"
    monkeypatch.setattr(gu, "get_github", lambda: MagicMock())
    monkeypatch.setattr(gu, "get_owner", lambda gh, org: MagicMock())
    monkeypatch.setattr(gu, "create_repo", lambda owner, n, d, p, force=False: fake_repo)
    monkeypatch.setattr(gu, "add_file", lambda *a, **k: None)

    # 1. Local wiring succeeds, but the mocked GitHub URL cannot be pushed.
    res_ok = _run(
        [
            "create",
            "clone-svc",
            "-l",
            "python",
            "-r",
            "github",
            "--create",
            "--clone",
            "--no-graphify",
        ]
    )
    assert res_ok.exit_code == 1, res_ok.stdout
    hooks_ok = "\n".join(
        _section_lines(res_ok.stdout, "Hook & remote status (actual results)")
    )
    assert "Skipped initial push: git push failed" in res_ok.stdout
    assert "GitHub remote: partial / pending" in hooks_ok
    assert "GitHub remote: ran" not in hooks_ok

    # 2. If local git hooks fail during --clone, status is partial/pending, never full success
    monkeypatch.setattr(
        cli_mod,
        "run_post_hooks",
        lambda *a, **k: ["Skipped git init: git unavailable"],
    )
    res_partial = _run(
        [
            "create",
            "clone-partial",
            "-l",
            "python",
            "-r",
            "github",
            "--create",
            "--clone",
            "--no-graphify",
        ]
    )
    assert res_partial.exit_code == 1, res_partial.stdout
    hooks_partial = "\n".join(
        _section_lines(res_partial.stdout, "Hook & remote status (actual results)")
    )
    assert "GitHub remote: partial / pending" in hooks_partial
    unverified_partial = "\n".join(
        _section_lines(res_partial.stdout, "Unverified / pending items")
    )
    assert "local git remote/commit/push: pending / incomplete" in unverified_partial


def test_create_no_graphify_with_outputs_dir_graphify_out_does_not_mislabel_as_graphify(
    tmp_path: Path,
):
    """P2 regression: when `--outputs-dir graphify-out --no-graphify` is passed,
    the composer creates `graphify-out/.gitkeep` as the custom outputs directory.
    `_echo_create_summary()` must report `graphify-out/` as the outputs directory,
    must state that Graphify is not selected (`--no-graphify`), and must NOT label
    `graphify-out/.gitkeep` as a Graphify placeholder, offer `graphify update .`,
    or report a Graphify knowledge graph as pending.
    """
    res = _run(
        [
            "create",
            "sample",
            "-l",
            "python",
            "--no-graphify",
            "--outputs-dir",
            "graphify-out",
            "--no-git",
        ]
    )
    assert res.exit_code == 0, res.stdout
    out = res.stdout

    # User-selected output file still exists on disk
    assert (tmp_path / "sample" / "graphify-out" / ".gitkeep").is_file()

    generated = "\n".join(_section_lines(out, "Generated and configured in sample/"))
    assert "graphify-out/" in generated
    assert "graphify-out/.gitkeep" not in generated
    assert "placeholder" not in generated.lower()
    assert "Graphify integration not selected (--no-graphify)" in generated

    hooks = "\n".join(_section_lines(out, "Hook & remote status (actual results)"))
    assert "graphify update .: not selected (--no-graphify)" in hooks

    steps = "\n".join(
        _section_lines(out, "First steps (user-run commands — not executed")
    )
    assert "graphify update ." not in steps

    unverified = "\n".join(_section_lines(out, "Unverified / pending items"))
    assert "graphify knowledge graph" not in unverified.lower()
    assert "placeholder" not in unverified.lower()


def test_readme_documents_preview_first_steps_and_support_boundaries():
    readme_path = Path(__file__).resolve().parents[1] / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    lowered = readme.lower()

    assert "projboot preview" in readme
    assert "not executed" in lowered or "does not execute" in lowered
    assert "helm lint ." in readme
    assert "npm run build" in readme
    assert "pytest" in readme
    assert "ruby -c config/application.rb" in readme
    assert "experimental" in lowered
