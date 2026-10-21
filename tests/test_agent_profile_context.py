"""C2 contract tests: AGENTS.md and stack-aware overlays provide accurate, profile-resolved
commands, layout, architecture layers, and change boundaries matching the actual generated files.
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
def test_python_profile_and_alias_document_executable_pkg_commands_and_hexagonal_layers(
    tmp_path: Path, lang: str
):
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
    assert "orders_svc" in scripts
    assert "appstarter" not in scripts

    # Real hexagonal architecture layer packages exist on disk
    for layer in ("domain", "ports", "adapters"):
        assert (proj / "src" / "orders_svc" / layer / "__init__.py").is_file()

    agents_md = (proj / "AGENTS.md").read_text(encoding="utf-8")
    cmd_fields = _extract_command_fields(agents_md)
    assert {"setup", "run", "test", "build"} <= set(cmd_fields.keys())

    assert "pip install -e ." in cmd_fields["setup"]
    assert "orders_svc" in cmd_fields["run"]
    assert "python -m orders_svc" in cmd_fields["run"]
    assert "pytest" in cmd_fields["test"]
    assert "python -m build" in cmd_fields["build"]

    # Execute the documented module entrypoint and pytest against the materialized project
    env = dict(os.environ)
    env["PYTHONPATH"] = str(proj / "src")
    run_proc = subprocess.run(
        [sys.executable, "-m", "orders_svc"],
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


@pytest.mark.parametrize(
    ("arch", "expected_layers"),
    [
        ("hexagonal", ("domain", "ports", "adapters")),
        ("clean-architecture", ("domain", "use_cases", "interfaces", "infrastructure")),
        ("layered", ("api", "services", "repositories")),
    ],
)
def test_structural_arch_layers_scaffolded_for_python_and_typescript(
    tmp_path: Path, arch: str, expected_layers: tuple[str, ...]
):
    preset = PresetConfig(name="arch-test", arch=arch, agents=["claude"])
    py_files = compose_project_files(
        name="billing-api",
        description="Billing API",
        lang="python",
        preset=preset,
        include_graphify=False,
    )
    for layer in expected_layers:
        assert f"src/billing_api/{layer}/__init__.py" in py_files
        assert f"src/billing_api/{layer}/" in py_files["AGENTS.md"]

    ts_files = compose_project_files(
        name="billing-ts",
        description="Billing TS",
        lang="typescript",
        preset=preset,
        include_graphify=False,
    )
    for layer in expected_layers:
        assert f"src/{layer}/index.ts" in ts_files
        assert f"src/{layer}/" in ts_files["AGENTS.md"]


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


def test_rails_template_is_removed(tmp_path: Path):
    preset = PresetConfig(name="default")
    with pytest.raises(KeyError, match="Unknown template 'rails'"):
        compose_project_files(
            name="rails-demo",
            description="Rails demo",
            lang="rails",
            preset=preset,
            include_graphify=False,
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


@pytest.mark.parametrize("lang", ["python", "python-microservice", "typescript", "helm-chart", "none"])
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

    # Thin overlays reference AGENTS.md, include stack hints, and do not invent foreign toolchain commands
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
