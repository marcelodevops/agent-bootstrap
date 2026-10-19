"""Behavioral contract tests for generated AI assistant adapter artifacts (C1)."""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path

import yaml

from bootstrapper.agents import SUPPORTED_AGENTS
from bootstrapper.composer import compose_project_files
from bootstrapper.presets import PresetConfig


def _split_frontmatter(markdown_text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter delimited by leading `---` markers and return (data, body)."""
    assert markdown_text.startswith("---\n"), "Expected leading YAML frontmatter delimiter"
    _, rest = markdown_text.split("---\n", 1)
    assert "\n---\n" in rest, "Expected closing YAML frontmatter delimiter"
    raw_yaml, body = rest.split("\n---\n", 1)
    parsed = yaml.safe_load(raw_yaml)
    assert isinstance(parsed, dict), "Frontmatter must decode to a YAML mapping"
    return parsed, body


def test_cursor_rule_frontmatter_parses_as_valid_yaml_with_glob_and_always_apply():
    preset = PresetConfig(
        name="custom",
        arch="hexagonal",
        outputs_dir="artifacts/out",
        scripts_dir="hack/bin",
        prompts_file="docs/PROMPTS.md",
        agents=["cursor"],
    )
    files = compose_project_files(
        name="orders-svc",
        description="Orders service",
        lang="python",
        preset=preset,
        include_graphify=False,
    )

    assert ".cursor/rules/project.mdc" in files
    frontmatter, body = _split_frontmatter(files[".cursor/rules/project.mdc"])

    assert frontmatter.get("alwaysApply") is True
    assert isinstance(frontmatter.get("description"), str)
    assert "orders-svc" in frontmatter["description"]

    globs = frontmatter.get("globs")
    if isinstance(globs, str):
        patterns = [globs.strip()]
    elif isinstance(globs, list):
        patterns = [str(item).strip() for item in globs]
    else:
        patterns = []

    assert patterns and all(patterns), "Expected at least one non-empty glob pattern"
    assert any(fnmatch.fnmatch("src/main.py", pat) for pat in patterns)

    # Conventions remain in the rule body
    assert "hexagonal" in body
    assert "artifacts/out/" in body
    assert "hack/bin/" in body
    assert "docs/PROMPTS.md" in body


def test_claude_settings_parses_without_unsupported_convention_keys_while_markdown_keeps_conventions():
    preset = PresetConfig(
        name="custom",
        arch="clean-arch",
        outputs_dir="build/reports",
        scripts_dir="tools/maint",
        prompts_file="ops/PROMPTS.md",
        agents=["claude"],
    )
    files = compose_project_files(
        name="billing-api",
        description="Billing API",
        lang="python",
        preset=preset,
        include_graphify=False,
    )

    assert ".claude/settings.json" in files
    settings = json.loads(files[".claude/settings.json"])
    assert isinstance(settings, dict)

    # Unsupported keys must not be emitted in .claude/settings.json
    unsupported_keys = {"project", "conventions", "outputsDir", "scriptsDir", "promptsFile"}
    assert unsupported_keys.isdisjoint(settings.keys())

    # Project conventions remain available in CLAUDE.md and AGENTS.md
    for doc_path in ("CLAUDE.md", "AGENTS.md"):
        content = files[doc_path]
        assert "billing-api" in content
        assert "clean-arch" in content
        assert "build/reports/" in content
        assert "tools/maint/" in content
        assert "ops/PROMPTS.md" in content


def test_combined_adapters_render_and_decode_on_disk(tmp_path: Path):
    preset = PresetConfig(
        name="all-agents",
        arch="layered",
        outputs_dir="outputs",
        scripts_dir="scripts",
        prompts_file="PROMPTS.md",
        agents=list(SUPPORTED_AGENTS),
    )
    files = compose_project_files(
        name="multi-agent-demo",
        description="Multi-agent scaffold",
        lang="none",
        preset=preset,
        include_graphify=False,
    )

    for rel_path, content in files.items():
        dest = tmp_path / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    expected_paths = (
        "AGENTS.md",
        "CLAUDE.md",
        ".claude/settings.json",
        ".github/copilot-instructions.md",
        ".github/prompts/bootstrap.prompt.md",
        ".codeassistant/instructions.md",
        ".cursor/rules/project.mdc",
    )
    for rel in expected_paths:
        assert (tmp_path / rel).is_file(), f"Missing generated adapter file {rel}"

    # Decode structured formats from disk
    claude_settings = json.loads((tmp_path / ".claude/settings.json").read_text(encoding="utf-8"))
    assert isinstance(claude_settings, dict)

    cursor_fm, _ = _split_frontmatter((tmp_path / ".cursor/rules/project.mdc").read_text(encoding="utf-8"))
    assert cursor_fm["alwaysApply"] is True

    copilot_fm, _ = _split_frontmatter(
        (tmp_path / ".github/prompts/bootstrap.prompt.md").read_text(encoding="utf-8")
    )
    assert "multi-agent-demo" in copilot_fm["description"]


def test_readme_documents_codeassistant_legacy_scope_and_static_verification_boundary():
    readme_path = Path(__file__).resolve().parents[1] / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8").lower()
    assert "codeassistant" in readme_text
    assert "custom" in readme_text or "legacy" in readme_text
    assert "static" in readme_text
