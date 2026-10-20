"""C3 behavioral tests: coherent skills, memory, user-store boundaries, and optional Graphify."""

from __future__ import annotations

import inspect
from pathlib import Path
import re
from unittest.mock import patch

import pytest

from bootstrapper import agents, composer, presets
from bootstrapper.agents import SUPPORTED_AGENTS
from bootstrapper.composer import _find_graphify, compose_project_files, run_post_hooks
from bootstrapper.presets import PresetConfig, init_config_dir, load_user_store_files


def _extract_section_paths(markdown: str, heading: str) -> list[str]:
    """Return backticked file/dir tokens under a given `## <heading>` section."""
    pattern = rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)"
    match = re.search(pattern, markdown, flags=re.MULTILINE | re.DOTALL)
    if not match:
        return []
    section = match.group(1)
    return re.findall(r"`([^`\n]+)`", section)


def test_no_graphify_omits_builtin_graphify_while_preserving_custom_user_store_graphify_files_and_lines(
    tmp_path: Path,
):
    """--no-graphify must omit builtin Graphify artifacts/mandates structurally
    without deleting user-authored files or lines that mention graphify.
    """
    config_dir = tmp_path / "projboot_home"
    custom_remember = config_dir / "remember" / "graphify-evaluation.md"
    custom_remember.parent.mkdir(parents=True, exist_ok=True)
    custom_remember.write_text(
        "# Graphify Evaluation for $name\n"
        "We evaluated graphify in $outputs_dir/ and decided to keep this custom note.\n"
        "Literal line with graphify must survive --no-graphify.\n",
        encoding="utf-8",
    )

    custom_skill = config_dir / "skills" / "graphify-migration" / "SKILL.md"
    custom_skill.parent.mkdir(parents=True, exist_ok=True)
    custom_skill.write_text(
        "---\n"
        "name: graphify-migration\n"
        "description: Custom skill mentioning graphify for $name\n"
        "---\n\n"
        "Keep custom graphify migration notes in $scripts_dir/.\n",
        encoding="utf-8",
    )

    preset = PresetConfig(
        name="custom",
        arch="hexagonal",
        outputs_dir="custom-out",
        scripts_dir="custom-scripts",
        prompts_file="docs/PROMPTS.md",
        agents=list(SUPPORTED_AGENTS),
    )

    files = compose_project_files(
        name="orders-app",
        description="Orders application",
        lang="python",
        preset=preset,
        config_dir=config_dir,
        include_graphify=False,
    )

    # 1. Builtin Graphify placeholder and builtin mandates are omitted
    assert "graphify-out/.gitkeep" not in files
    for builtin_path in (
        "AGENTS.md",
        "docs/PROMPTS.md",
        "CLAUDE.md",
        ".github/copilot-instructions.md",
        ".github/prompts/bootstrap.prompt.md",
        ".codeassistant/instructions.md",
        ".cursor/rules/project.mdc",
        ".agents/skills/project-conventions/SKILL.md",
    ):
        assert builtin_path in files, f"Expected builtin artifact {builtin_path}"
        assert "graphify" not in files[builtin_path].lower(), (
            f"Builtin artifact {builtin_path} still mentions graphify under --no-graphify"
        )

    # Non-graphify prompt bodies and copilot skills pointer must remain intact
    assert "AGENTS.md" in files["docs/PROMPTS.md"]
    assert "hexagonal" in files["docs/PROMPTS.md"]
    assert ".agents/skills/" in files[".github/copilot-instructions.md"]

    # 2. Custom user-store file paths and lines mentioning graphify survive intact
    assert ".remember/graphify-evaluation.md" in files
    assert (
        files[".remember/graphify-evaluation.md"]
        == "# Graphify Evaluation for orders-app\n"
        "We evaluated graphify in custom-out/ and decided to keep this custom note.\n"
        "Literal line with graphify must survive --no-graphify.\n"
    )

    assert ".agents/skills/graphify-migration/SKILL.md" in files
    assert (
        files[".agents/skills/graphify-migration/SKILL.md"]
        == "---\n"
        "name: graphify-migration\n"
        "description: Custom skill mentioning graphify for orders-app\n"
        "---\n\n"
        "Keep custom graphify migration notes in custom-scripts/.\n"
    )


def test_graphify_enabled_distinguishes_placeholder_from_populated_graph_and_avoids_claiming_installation(
    tmp_path: Path,
):
    """When Graphify is enabled, generated instructions must distinguish the
    `graphify-out/.gitkeep` placeholder from a populated graph (`graphify-out/graph.json`)
    and state that the external `graphify` CLI is an optional prerequisite rather than
    claiming it is already installed.
    """
    preset = PresetConfig(
        name="default",
        arch="modular",
        outputs_dir="outputs",
        scripts_dir="scripts",
        prompts_file="PROMPTS.md",
        agents=list(SUPPORTED_AGENTS),
    )
    files = compose_project_files(
        name="graph-enabled-demo",
        description="Graph enabled project",
        lang="python",
        preset=preset,
        config_dir=tmp_path / "empty_store",
        include_graphify=True,
    )

    assert "graphify-out/.gitkeep" in files
    agents_md = files["AGENTS.md"]
    lower_agents = agents_md.lower()

    assert "graphify-out/.gitkeep" in agents_md or "placeholder" in lower_agents
    assert "graphify-out/graph.json" in agents_md
    assert "not install" in lower_agents or "external" in lower_agents or "if installed" in lower_agents


def test_custom_user_store_keeps_default_artifacts_and_coherent_references(tmp_path: Path):
    """When a custom user store adds custom remember/skill files (without calling
    config-init first), default memory/skill artifacts and custom artifacts are
    both present and every path listed in AGENTS.md Generated Project Layout exists.
    """
    config_dir = tmp_path / "user_store"
    (config_dir / "remember").mkdir(parents=True)
    (config_dir / "remember" / "domain-glossary.md").write_text(
        "# Domain Glossary for $name\n", encoding="utf-8"
    )
    (config_dir / "skills" / "api-design").mkdir(parents=True)
    (config_dir / "skills" / "api-design" / "SKILL.md").write_text(
        "---\nname: api-design\ndescription: API conventions for $name\n---\n",
        encoding="utf-8",
    )

    preset = PresetConfig(
        name="custom",
        arch="clean-architecture",
        outputs_dir="artifacts/out",
        scripts_dir="tools/scripts",
        prompts_file="docs/PROMPTS.md",
        agents=list(SUPPORTED_AGENTS),
    )
    files = compose_project_files(
        name="coherent-store",
        description="Coherent store test",
        lang="typescript",
        preset=preset,
        config_dir=config_dir,
        include_graphify=True,
    )

    # Both default and custom memory/skill artifacts exist
    assert ".remember/MEMORY.md" in files
    assert ".remember/decisions.md" in files
    assert ".remember/domain-glossary.md" in files
    assert ".agents/skills/project-conventions/SKILL.md" in files
    assert ".agents/skills/api-design/SKILL.md" in files

    # Materialize and verify every Generated Project Layout path in AGENTS.md exists on disk
    proj = tmp_path / "materialized"
    for rel, content in files.items():
        dest = proj / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    layout_paths = _extract_section_paths(files["AGENTS.md"], "Generated Project Layout")
    assert layout_paths
    for rel in layout_paths:
        assert (proj / rel.rstrip("/")).exists(), (
            f"AGENTS.md referenced {rel!r} in Generated Project Layout, but it does not exist"
        )
    assert ".remember/MEMORY.md" in layout_paths
    assert ".remember/decisions.md" in layout_paths
    assert ".agents/skills/project-conventions/SKILL.md" in layout_paths


def test_conditional_references_adapt_when_custom_store_replaces_default_files(tmp_path: Path):
    """Even if a caller supplies a custom store dictionary that replaces default
    memory/skill paths, generated builtin references in AGENTS.md, PROMPTS.md,
    and overlays must target only the existing generated artifacts.
    """
    custom_only_store = {
        ".remember/team-handbook.md": "# Team Handbook for $name\n",
        ".agents/skills/custom-workflow/SKILL.md": "# Custom workflow for $name\n",
    }
    preset = PresetConfig(
        name="custom",
        arch="modular",
        outputs_dir="outputs",
        scripts_dir="scripts",
        prompts_file="PROMPTS.md",
        agents=list(SUPPORTED_AGENTS),
    )
    with patch(
        "bootstrapper.agents.load_user_store_files", return_value=custom_only_store
    ):
        files = compose_project_files(
            name="replaced-store",
            description="Replaced store test",
            lang="python",
            preset=preset,
            include_graphify=False,
        )

    assert ".remember/MEMORY.md" not in files["AGENTS.md"]
    assert ".remember/team-handbook.md" in files["AGENTS.md"]
    assert ".agents/skills/custom-workflow/SKILL.md" in files["AGENTS.md"]
    assert ".remember/team-handbook.md" in files["PROMPTS.md"]
    assert ".remember/team-handbook.md" in files["CLAUDE.md"]
    assert ".remember/team-handbook.md" in files[".github/copilot-instructions.md"]
    assert ".remember/team-handbook.md" in files[".codeassistant/instructions.md"]
    assert ".remember/team-handbook.md" in files[".cursor/rules/project.mdc"]


def test_config_init_store_respects_no_graphify_when_default_skill_unedited_and_preserves_when_edited(
    tmp_path: Path,
):
    """If a user runs `init_config_dir` and does not edit the default skill,
    running with `include_graphify=False` must omit the builtin Graphify
    mandate from `.agents/skills/project-conventions/SKILL.md`. If the user
    edits that skill to mention graphify, their custom edit must survive.
    """
    config_dir = tmp_path / "initialized_store"
    init_config_dir(config_dir)

    preset = PresetConfig(name="default", agents=["claude"])
    files = compose_project_files(
        name="init-plain-demo",
        description="Initialized store without graphify",
        lang="none",
        preset=preset,
        config_dir=config_dir,
        include_graphify=False,
    )

    skill_body = files[".agents/skills/project-conventions/SKILL.md"]
    assert "graphify" not in skill_body.lower()

    # Now user customizes project-conventions/SKILL.md with their own graphify note
    (config_dir / "skills" / "project-conventions" / "SKILL.md").write_text(
        "# Custom conventions for $name\nUser-authored graphify note stays.\n",
        encoding="utf-8",
    )
    edited_files = compose_project_files(
        name="init-plain-demo",
        description="Initialized store with user-edited skill",
        lang="none",
        preset=preset,
        config_dir=config_dir,
        include_graphify=False,
    )
    assert (
        "User-authored graphify note stays."
        in edited_files[".agents/skills/project-conventions/SKILL.md"]
    )


def test_user_store_secrets_boundary_blocks_real_env_and_allows_examples(tmp_path: Path):
    """Real `.env` and secret env variants in user store must never be copied,
    while `.env.example`, `.env.sample`, `.env.template`, and `example.env` remain allowed.
    """
    config_dir = tmp_path / "secret_store"
    rem = config_dir / "remember"
    sk = config_dir / "skills" / "deploy-skill"
    rem.mkdir(parents=True)
    sk.mkdir(parents=True)

    # Forbidden secret/dotenv files and hidden dirs
    (rem / ".env").write_text("SECRET_KEY=real-secret\n", encoding="utf-8")
    (rem / ".env.local").write_text("LOCAL_TOKEN=real-token\n", encoding="utf-8")
    (rem / ".env.production").write_text("PROD_PASSWORD=real-pass\n", encoding="utf-8")
    (sk / ".env").write_text("SKILL_SECRET=top-secret\n", encoding="utf-8")
    (sk / "secrets.env").write_text("API_KEY=real-key\n", encoding="utf-8")
    hidden_dir = sk / ".private"
    hidden_dir.mkdir()
    (hidden_dir / "credentials.txt").write_text("PRIVATE=1\n", encoding="utf-8")

    # Allowed shareable templates and normal custom files
    (rem / ".env.example").write_text("APP_NAME=$name\n", encoding="utf-8")
    (sk / ".env.sample").write_text("SAMPLE_VAR=$name\n", encoding="utf-8")
    (sk / ".env.template").write_text("TEMPLATE_VAR=$outputs_dir\n", encoding="utf-8")
    (sk / "example.env").write_text("EXAMPLE_ONLY=true\n", encoding="utf-8")
    (sk / "SKILL.md").write_text("# Deploy skill for $name\n", encoding="utf-8")

    store_files = load_user_store_files(config_dir)

    # Real .env and hidden dir files must not be loaded
    assert ".remember/.env" not in store_files
    assert ".remember/.env.local" not in store_files
    assert ".remember/.env.production" not in store_files
    assert ".agents/skills/deploy-skill/.env" not in store_files
    assert ".agents/skills/deploy-skill/secrets.env" not in store_files
    assert ".agents/skills/deploy-skill/.private/credentials.txt" not in store_files
    for body in store_files.values():
        assert "real-secret" not in body
        assert "real-token" not in body
        assert "real-pass" not in body
        assert "top-secret" not in body
        assert "real-key" not in body

    # Shareable example/sample/template files remain allowed
    assert ".remember/.env.example" in store_files
    assert ".agents/skills/deploy-skill/.env.sample" in store_files
    assert ".agents/skills/deploy-skill/.env.template" in store_files
    assert ".agents/skills/deploy-skill/example.env" in store_files
    assert ".agents/skills/deploy-skill/SKILL.md" in store_files


def test_user_store_rejects_symlinks_to_disguised_secret_targets_and_outside_files(
    tmp_path: Path,
):
    """P1 regression: symlinks in `remember/` or `skills/` (including a benignly
    named `remember/deployment.md -> outside/.env`, an in-store symlink to `.env`,
    an outside file symlink, or a symlinked directory) must never be read or copied
    into generated project files, while regular `.env.example`/`.env.sample`/`.env.template`
    files remain allowed.
    """
    outside = tmp_path / "outside"
    outside.mkdir(parents=True)
    outside_env = outside / ".env"
    outside_env.write_text("SYNTHETIC_OUTSIDE_SECRET=do-not-copy-1\n", encoding="utf-8")
    outside_doc = outside / "external.md"
    outside_doc.write_text("SYNTHETIC_OUTSIDE_DOC=do-not-copy-2\n", encoding="utf-8")

    config_dir = tmp_path / "symlink_store"
    rem = config_dir / "remember"
    sk = config_dir / "skills" / "safe-skill"
    rem.mkdir(parents=True)
    sk.mkdir(parents=True)

    # Synthetic inside .env
    inside_env = rem / ".env"
    inside_env.write_text("SYNTHETIC_INSIDE_SECRET=do-not-copy-3\n", encoding="utf-8")

    # Symlinks disguised with benign Markdown/skill names
    (rem / "deployment.md").symlink_to(outside_env)
    (rem / "local-ref.md").symlink_to(inside_env)
    (rem / "external-notes.md").symlink_to(outside_doc)
    (config_dir / "skills" / "linked-outside").symlink_to(
        outside, target_is_directory=True
    )

    # Regular allowed shareable env templates and regular files
    (rem / ".env.example").write_text("APP_NAME=$name\n", encoding="utf-8")
    (sk / ".env.sample").write_text("SAMPLE_KEY=$name\n", encoding="utf-8")
    (sk / ".env.template").write_text("TEMPLATE_KEY=$outputs_dir\n", encoding="utf-8")
    (sk / "SKILL.md").write_text("# Safe skill for $name\n", encoding="utf-8")

    store_files = load_user_store_files(config_dir)

    assert ".remember/deployment.md" not in store_files
    assert ".remember/local-ref.md" not in store_files
    assert ".remember/external-notes.md" not in store_files
    assert not any(k.startswith(".agents/skills/linked-outside/") for k in store_files)

    composed = compose_project_files(
        name="symlink-guard-app",
        description="Symlink guard test",
        lang="python",
        preset=PresetConfig(name="default", agents=["claude"]),
        config_dir=config_dir,
        include_graphify=False,
    )
    assert ".remember/deployment.md" not in composed
    assert ".remember/local-ref.md" not in composed
    assert ".remember/external-notes.md" not in composed
    for body in composed.values():
        assert "do-not-copy-1" not in body
        assert "do-not-copy-2" not in body
        assert "do-not-copy-3" not in body

    # Regular shareable templates and skill files remain preserved
    assert ".remember/.env.example" in composed
    assert ".agents/skills/safe-skill/.env.sample" in composed
    assert ".agents/skills/safe-skill/.env.template" in composed
    assert ".agents/skills/safe-skill/SKILL.md" in composed


def test_portable_graphify_discovery_removes_hardcoded_author_path_and_uses_path_or_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """`_find_graphify` must not hardcode `/Users/mac` in source code and must
    discover `graphify` via `PATH` first, then an executable `<HOME>/.local/bin/graphify`.
    """
    for module in (agents, composer, presets):
        source = inspect.getsource(module)
        assert "/Users/mac" not in source, f"Hardcoded /Users/mac path found in {module.__name__}"

    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    # 1. Neither PATH nor ~/.local/bin/graphify has the binary
    with patch("bootstrapper.composer.shutil.which", return_value=None):
        assert _find_graphify() is None

    # 2. Home-relative fallback ~/.local/bin/graphify must be executable to be discovered
    local_bin = fake_home / ".local" / "bin"
    local_bin.mkdir(parents=True)
    fallback_bin = local_bin / "graphify"
    fallback_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fallback_bin.chmod(0o644)

    with patch("bootstrapper.composer.shutil.which", return_value=None):
        assert _find_graphify() is None

    fallback_bin.chmod(0o755)
    with patch("bootstrapper.composer.shutil.which", return_value=None):
        assert _find_graphify() == str(fallback_bin)

    # 3. PATH entry takes precedence over ~/.local/bin/graphify
    with patch("bootstrapper.composer.shutil.which", return_value="/opt/custom/bin/graphify"):
        assert _find_graphify() == "/opt/custom/bin/graphify"

    # 4. run_post_hooks uses discovered binary without installing or invoking npx/TypeScript graphify
    calls: list[list[str]] = []

    def fake_run(cmd, cwd, check, capture_output, text):
        calls.append(cmd)

    with (
        patch("bootstrapper.composer.shutil.which", return_value=None),
        patch("bootstrapper.composer.subprocess.run", side_effect=fake_run),
    ):
        msgs = run_post_hooks(tmp_path, init_git=False, run_graphify=True)

    assert calls == [[str(fallback_bin), "update", "."]]
    assert any("Initialized graphify knowledge graph" in m for m in msgs)


def test_native_nonexecutable_home_fallback_does_not_raise_permission_error_in_run_post_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """P2 regression: with a real non-executable `<HOME>/.local/bin/graphify` and no
    mocked `subprocess.run`, `_find_graphify()` must not treat the non-executable file
    as an installed binary, and `run_post_hooks` must report a clean best-effort skip
    message rather than raising `PermissionError`. Even if a non-executable binary path
    is passed to `subprocess.run`, `run_post_hooks` must catch `PermissionError`/`OSError`.
    """
    fake_home = tmp_path / "fake_home"
    local_bin = fake_home / ".local" / "bin"
    local_bin.mkdir(parents=True)
    nonexec_bin = local_bin / "graphify"
    nonexec_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    nonexec_bin.chmod(0o644)

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("PATH", "")

    assert _find_graphify() is None

    target_dir = tmp_path / "project_target"
    target_dir.mkdir()

    # Real run_post_hooks (no subprocess.run mock) with non-executable home fallback
    msgs = run_post_hooks(target_dir, init_git=False, run_graphify=True)
    assert msgs == ["Skipped graphify update (graphify binary not found)"]

    # Even if a non-executable path were returned right before execution, real
    # subprocess.run PermissionError is handled as a best-effort skip message.
    with patch("bootstrapper.composer._find_graphify", return_value=str(nonexec_bin)):
        perm_msgs = run_post_hooks(target_dir, init_git=False, run_graphify=True)
    assert len(perm_msgs) == 1
    assert perm_msgs[0].startswith("Skipped graphify update:")
