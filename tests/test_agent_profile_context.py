"""C2 contract tests: AGENTS.md and thin overlays provide accurate, profile-resolved
commands, layout, and change boundaries matching the actual generated files.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib

import pytest

from bootstrapper.agents import SUPPORTED_AGENTS
from bootstrapper.composer import compose_project_files
from bootstrapper.presets import PresetConfig

HELM = shutil.which("helm")
RUBY = shutil.which("ruby")


def _materialize(tmp_path: Path, files: dict[str, str], subdir: str = "proj") -> Path:
    root = tmp_path / subdir
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return root


def _extract_command_fields(agents_md: str) -> dict[str, str]:
    """Parse `- **Setup**: ...`, `- **Run**: ...`, `- **Test**: ...`, `- **Build**: ...` lines."""
    fields: dict[str, str] = {}
    for key in ("Profile", "Setup", "Run", "Test", "Build"):
        match = re.search(rf"^-\s+\*\*{key}\*\*:\s*(.+)$", agents_md, flags=re.MULTILINE)
        if match:
            fields[key.lower()] = match.group(1).strip()
    return fields


def _extract_section_paths(markdown: str, heading: str) -> list[str]:
    """Return backticked file/dir tokens under a given `## <heading>` section."""
    pattern = rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)"
    match = re.search(pattern, markdown, flags=re.MULTILINE | re.DOTALL)
    if not match:
        return []
    section = match.group(1)
    return re.findall(r"`([^`\n]+)`", section)


@pytest.mark.parametrize("lang", ["python", "python-microservice"])
def test_python_profile_and_alias_document_executable_appstarter_commands(tmp_path: Path, lang: str):
    preset = PresetConfig(
        name="custom",
        arch="hexagonal",
        outputs_dir="artifacts/out",
        scripts_dir="hack/bin",
        prompts_file="docs/PROMPTS.md",
        agents=list(SUPPORTED_AGENTS),
    )
    files = compose_project_files(
        name="orders-svc",
        description="Orders service",
        lang=lang,
        preset=preset,
        include_graphify=False,
    )
    proj = _materialize(tmp_path, files, subdir=f"proj-{lang}")

    pyproject = tomllib.loads((proj / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject["project"]["scripts"]
    assert "appstarter" in scripts

    agents_md = (proj / "AGENTS.md").read_text(encoding="utf-8")
    cmd_fields = _extract_command_fields(agents_md)
    assert {"setup", "run", "test", "build"} <= set(cmd_fields.keys())

    assert "pip install -e ." in cmd_fields["setup"]
    assert "appstarter" in cmd_fields["run"]
    assert "python -m appstarter" in cmd_fields["run"]
    assert "pytest" in cmd_fields["test"]
    assert "python -m build" in cmd_fields["build"]

    # Execute the documented module entrypoint and pytest against the materialized project
    env = dict(os.environ)
    env["PYTHONPATH"] = str(proj / "src")
    run_proc = subprocess.run(
        [sys.executable, "-m", "appstarter"],
        cwd=proj,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run_proc.returncode == 0, run_proc.stdout + run_proc.stderr
    assert "Hello from orders-svc!" in run_proc.stdout

    test_proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=proj,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert test_proc.returncode == 0, test_proc.stdout + test_proc.stderr


def test_typescript_profile_documents_npm_build_and_start_without_invented_test_script(tmp_path: Path):
    preset = PresetConfig(name="default", agents=["claude", "gh-copilot", "cursor"])
    files = compose_project_files(
        name="ts-worker",
        description="TypeScript worker",
        lang="typescript",
        preset=preset,
        include_graphify=False,
    )
    proj = _materialize(tmp_path, files)

    pkg = json.loads((proj / "package.json").read_text(encoding="utf-8"))
    assert set(pkg["scripts"].keys()) == {"build", "start"}

    agents_md = (proj / "AGENTS.md").read_text(encoding="utf-8")
    cmd_fields = _extract_command_fields(agents_md)
    assert {"setup", "run", "test", "build"} <= set(cmd_fields.keys())

    assert "npm install" in cmd_fields["setup"]
    assert "npm run build" in cmd_fields["build"]
    assert "npm start" in cmd_fields["run"]
    assert "unavailable" in cmd_fields["test"].lower()
    assert "npm test" not in agents_md.lower()


def test_helm_profile_documents_lint_and_template_without_claiming_cluster_deploy(tmp_path: Path):
    preset = PresetConfig(name="default", agents=["claude", "cursor"])
    files = compose_project_files(
        name="payments-chart",
        description="Payments chart",
        lang="helm-chart",
        preset=preset,
        include_graphify=False,
    )
    proj = _materialize(tmp_path, files)
    agents_md = (proj / "AGENTS.md").read_text(encoding="utf-8")
    cmd_fields = _extract_command_fields(agents_md)
    assert {"setup", "run", "test", "build"} <= set(cmd_fields.keys())

    assert "helm lint ." in cmd_fields["test"]
    assert "helm template payments-chart ." in cmd_fields["build"]
    assert "unavailable" in cmd_fields["run"].lower()

    if HELM:
        lint_proc = subprocess.run(
            [HELM, "lint", "."],
            cwd=proj,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert lint_proc.returncode == 0, lint_proc.stdout + lint_proc.stderr

        tpl_proc = subprocess.run(
            [HELM, "template", "payments-chart", "."],
            cwd=proj,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert tpl_proc.returncode == 0, tpl_proc.stdout + tpl_proc.stderr


def _extract_ruby_syntax_commands(test_field: str) -> list[list[str]]:
    """Extract documented `ruby -c ...` command steps from the Test field."""
    code_spans = re.findall(r"`([^`\n]+)`", test_field)
    ruby_spans = [span for span in code_spans if "ruby -c" in span]
    assert ruby_spans, f"Expected documented `ruby -c` command in {test_field!r}"
    steps: list[list[str]] = []
    for part in ruby_spans[0].split("&&"):
        tokens = part.strip().split()
        assert tokens[:2] == ["ruby", "-c"], f"Unexpected command segment: {part!r}"
        steps.append(tokens)
    return steps


def test_rails_profile_states_experimental_non_runnable_limits_in_agents_md(tmp_path: Path):
    preset = PresetConfig(name="default", agents=["claude", "gh-copilot"])
    files = compose_project_files(
        name="rails-demo",
        description="Rails demo",
        lang="rails",
        preset=preset,
        include_graphify=False,
    )
    proj = _materialize(tmp_path, files)
    agents_md = (proj / "AGENTS.md").read_text(encoding="utf-8")
    cmd_fields = _extract_command_fields(agents_md)
    assert {"profile", "setup", "run", "test", "build"} <= set(cmd_fields.keys())

    assert "experimental" in cmd_fields["profile"].lower()
    assert "unavailable" in cmd_fields["setup"].lower()
    assert "unavailable" in cmd_fields["run"].lower()
    assert "unavailable" in cmd_fields["test"].lower()
    assert "unavailable" in cmd_fields["build"].lower()
    assert "rails server" not in agents_md.lower()

    steps = _extract_ruby_syntax_commands(cmd_fields["test"])
    assert len(steps) == 2, f"Expected two separate `ruby -c` invocations, got {steps}"
    for tokens in steps:
        assert len(tokens) == 3, f"`ruby -c` only checks the first file argument; got {tokens}"

    if RUBY:
        for tokens in steps:
            ruby_proc = subprocess.run(
                [RUBY, *tokens[1:]],
                cwd=proj,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert ruby_proc.returncode == 0, ruby_proc.stdout + ruby_proc.stderr


@pytest.mark.skipif(RUBY is None, reason="ruby binary required for native syntax check")
def test_rails_documented_syntax_check_catches_invalid_second_file(tmp_path: Path):
    """Regression: `ruby -c a.rb b.rb` ignores `b.rb` as argv; the documented
    command in AGENTS.md must check each file so a broken second file fails."""
    preset = PresetConfig(name="default", agents=["claude"])
    files = compose_project_files(
        name="rails-broken-second",
        description="Rails syntax regression",
        lang="rails",
        preset=preset,
        include_graphify=False,
    )
    proj = _materialize(tmp_path, files)
    agents_md = (proj / "AGENTS.md").read_text(encoding="utf-8")
    cmd_fields = _extract_command_fields(agents_md)
    steps = _extract_ruby_syntax_commands(cmd_fields["test"])

    # Corrupt the second generated Ruby file while leaving config/application.rb valid
    (proj / "app/controllers/application_controller.rb").write_text(
        "class ApplicationController <\n", encoding="utf-8"
    )

    codes: list[int] = []
    for tokens in steps:
        proc = subprocess.run(
            [RUBY, *tokens[1:]],
            cwd=proj,
            capture_output=True,
            text=True,
            timeout=30,
        )
        codes.append(proc.returncode)

    assert any(code != 0 for code in codes), (
        f"Documented syntax check {steps} returned 0 despite invalid controller syntax"
    )


def test_none_profile_invents_no_runtime_or_test_toolchain(tmp_path: Path):
    preset = PresetConfig(name="default", agents=list(SUPPORTED_AGENTS))
    files = compose_project_files(
        name="agent-notes",
        description="Notes workspace",
        lang="none",
        preset=preset,
        include_graphify=False,
    )
    proj = _materialize(tmp_path, files)
    agents_md = (proj / "AGENTS.md").read_text(encoding="utf-8")
    cmd_fields = _extract_command_fields(agents_md)
    assert {"setup", "run", "test", "build"} <= set(cmd_fields.keys())

    for key in ("setup", "run", "test", "build"):
        assert "unavailable" in cmd_fields[key].lower()

    lowered = agents_md.lower()
    for fabricated in ("pytest", "npm ", "helm ", "rails ", "bundle "):
        assert fabricated not in lowered


@pytest.mark.parametrize("lang", ["python", "python-microservice", "typescript", "helm-chart", "rails", "none"])
def test_documented_layout_paths_and_thin_overlays_match_generated_tree(tmp_path: Path, lang: str):
    preset = PresetConfig(
        name="custom",
        arch="clean-hexagonal",
        outputs_dir="custom-out/reports",
        scripts_dir="ops/scripts",
        prompts_file="docs/PROMPTS.md",
        agents=list(SUPPORTED_AGENTS),
    )
    files = compose_project_files(
        name="layout-check",
        description="Verify layout and overlays",
        lang=lang,
        preset=preset,
        include_graphify=False,
    )
    proj = _materialize(tmp_path, files, subdir=f"tree-{lang}")
    agents_md = (proj / "AGENTS.md").read_text(encoding="utf-8")

    layout_paths = _extract_section_paths(agents_md, "Generated Project Layout")
    assert layout_paths, f"Expected Generated Project Layout paths in AGENTS.md for {lang}"
    for rel in layout_paths:
        target = proj / rel.rstrip("/")
        assert target.exists(), f"AGENTS.md listed {rel!r} for profile {lang}, but it was not generated"

    # Change boundaries and custom conventions preserved
    assert "## Change Boundaries" in agents_md
    assert "clean-hexagonal" in agents_md
    assert "custom-out/reports/" in agents_md
    assert "ops/scripts/" in agents_md
    assert "docs/PROMPTS.md" in agents_md

    # Thin overlays reference AGENTS.md and do not invent foreign toolchain commands
    for overlay_rel in (
        "CLAUDE.md",
        ".github/copilot-instructions.md",
        ".github/prompts/bootstrap.prompt.md",
        ".codeassistant/instructions.md",
        ".cursor/rules/project.mdc",
    ):
        text = (proj / overlay_rel).read_text(encoding="utf-8")
        assert "AGENTS.md" in text
        for tool_cmd in ("pytest", "npm install", "helm lint", "rails server"):
            assert tool_cmd not in text.lower()
