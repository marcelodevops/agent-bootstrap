import pytest

from bootstrapper.agents import (
    SUPPORTED_AGENTS,
    agent_overlay_files,
    universal_harness_files,
)
from bootstrapper.presets import PresetConfig
from bootstrapper.templates import render


def test_universal_harness_includes_graphify_remember_skills_and_custom_paths(tmp_path):
    preset = PresetConfig(
        name="custom",
        arch="hexagonal",
        outputs_dir="out/artifacts",
        scripts_dir="hack/scripts",
        prompts_file="docs/PROMPTS.md",
    )
    raw_files = universal_harness_files(preset, config_dir=tmp_path)
    assert "AGENTS.md" in raw_files
    assert "graphify-out/.gitkeep" in raw_files
    assert "out/artifacts/.gitkeep" in raw_files
    assert "hack/scripts/.gitkeep" in raw_files
    assert "docs/PROMPTS.md" in raw_files
    assert ".remember/MEMORY.md" in raw_files
    assert ".agents/skills/project-conventions/SKILL.md" in raw_files

    rendered_agents = render(
        raw_files["AGENTS.md"],
        name="demo-ai",
        description="AI service",
        arch=preset.arch,
        outputs_dir=preset.outputs_dir,
        scripts_dir=preset.scripts_dir,
        prompts_file=preset.prompts_file,
    )
    assert "hexagonal" in rendered_agents
    assert "out/artifacts/" in rendered_agents
    assert "hack/scripts/" in rendered_agents
    assert "docs/PROMPTS.md" in rendered_agents
    assert "graphify-out/" in rendered_agents


def test_agent_overlays_for_claude_and_copilot():
    overlays = agent_overlay_files(["claude", "gh-copilot"])
    assert "CLAUDE.md" in overlays
    assert ".claude/settings.json" in overlays
    assert ".github/copilot-instructions.md" in overlays
    assert ".github/prompts/bootstrap.prompt.md" in overlays


def test_agent_overlays_for_codeassistant_and_cursor():
    overlays = agent_overlay_files(["codeassistant", "cursor"])
    assert ".codeassistant/instructions.md" in overlays
    assert ".cursor/rules/project.mdc" in overlays


def test_unknown_agent_raises_key_error():
    with pytest.raises(KeyError, match="Unknown agent 'unknown-bot'"):
        agent_overlay_files(["unknown-bot"])


def test_supported_agents_constant():
    assert set(SUPPORTED_AGENTS) == {"claude", "gh-copilot", "codeassistant", "cursor"}
