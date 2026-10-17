from pathlib import Path
import pytest

from bootstrapper.presets import (
    PresetConfig,
    get_config_dir,
    init_config_dir,
    load_presets,
    load_user_store_files,
    resolve_preset,
)


def test_get_config_dir_uses_env(monkeypatch, tmp_path):
    custom = tmp_path / "custom_projboot"
    monkeypatch.setenv("PROJBOOT_HOME", str(custom))
    assert get_config_dir() == custom


def test_builtin_presets_loaded_when_no_config_file(tmp_path):
    presets = load_presets(tmp_path)
    assert "default" in presets
    assert "clean-arch" in presets
    default = presets["default"]
    assert default.arch == "modular"
    assert default.outputs_dir == "outputs"
    assert default.scripts_dir == "scripts"
    assert default.prompts_file == "PROMPTS.md"


def test_user_presets_toml_overrides_and_adds(tmp_path):
    (tmp_path / "presets.toml").write_text(
        '[presets.default]\n'
        'outputs_dir = "custom-out"\n\n'
        '[presets.go-hex]\n'
        'arch = "hexagonal"\n'
        'outputs_dir = "dist/out"\n'
        'scripts_dir = "hack"\n'
        'prompts_file = "docs/prompts.md"\n'
        'agents = ["claude", "gh-copilot"]\n'
    )
    presets = load_presets(tmp_path)
    assert presets["default"].outputs_dir == "custom-out"
    assert presets["default"].scripts_dir == "scripts"
    hex_p = presets["go-hex"]
    assert hex_p == PresetConfig(
        name="go-hex",
        arch="hexagonal",
        outputs_dir="dist/out",
        scripts_dir="hack",
        prompts_file="docs/prompts.md",
        agents=["claude", "gh-copilot"],
    )


def test_resolve_preset_cli_overrides_win(tmp_path):
    resolved = resolve_preset(
        "default",
        arch="event-driven",
        outputs_dir="build/out",
        scripts_dir="bin",
        prompts_file="AI_PROMPTS.md",
        agents=["claude"],
        config_dir=tmp_path,
    )
    assert resolved.arch == "event-driven"
    assert resolved.outputs_dir == "build/out"
    assert resolved.scripts_dir == "bin"
    assert resolved.prompts_file == "AI_PROMPTS.md"
    assert resolved.agents == ["claude"]


def test_resolve_preset_unknown_raises_key_error(tmp_path):
    with pytest.raises(KeyError, match="Unknown preset 'nonexistent'"):
        resolve_preset("nonexistent", config_dir=tmp_path)


def test_validate_rel_path_accepts_safe_relative():
    from bootstrapper.presets import validate_rel_path

    assert validate_rel_path("docs/PROMPTS.md", "x") == "docs/PROMPTS.md"
    assert validate_rel_path("out/artifacts", "x") == "out/artifacts"


@pytest.mark.parametrize("bad", ["../escape", "/abs/path", "~/home", "a/../../b"])
def test_validate_rel_path_rejects_unsafe(bad):
    from bootstrapper.presets import validate_rel_path

    with pytest.raises(ValueError):
        validate_rel_path(bad, "--outputs-dir")


def test_resolve_preset_rejects_escaping_outputs_dir(tmp_path):
    with pytest.raises(ValueError, match="must not contain"):
        resolve_preset("default", outputs_dir="../outside", config_dir=tmp_path)


def test_resolve_preset_rejects_absolute_prompts_file(tmp_path):
    with pytest.raises(ValueError, match="relative to the project root"):
        resolve_preset("default", prompts_file="/etc/passwd", config_dir=tmp_path)


def test_init_config_dir_and_load_user_store(tmp_path):
    created = init_config_dir(tmp_path)
    assert (tmp_path / "presets.toml").exists()
    assert len(created) >= 4

    # Add a custom skill and custom remember note in the user store
    custom_skill = tmp_path / "skills" / "my-skill" / "SKILL.md"
    custom_skill.parent.mkdir(parents=True, exist_ok=True)
    custom_skill.write_text("# Skill for $name\nOutputs in $outputs_dir\n")

    files = load_user_store_files(tmp_path)
    assert ".agents/skills/my-skill/SKILL.md" in files
    assert "$outputs_dir" in files[".agents/skills/my-skill/SKILL.md"]
    assert ".remember/MEMORY.md" in files
    assert ".remember/decisions.md" in files
