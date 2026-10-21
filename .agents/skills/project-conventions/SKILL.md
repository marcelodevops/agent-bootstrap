---
name: project-conventions
description: Core workspace layout, template safety, and verification rules for agent-bootstrap.
---

# Project Conventions for `agent-bootstrap`

1. **Single Composition Pipeline**: `create` and `preview` must always call `_resolve_options_and_compose()` and `_validate_write_plan()`.
2. **Dynamic Identifiers**: Use `$pkg_name` for Python package/module names and `$helm_name` for Helm chart names rather than hardcoded placeholders.
3. **Real Architecture Layers**: When `--arch` specifies `hexagonal`, `clean-architecture`, or `layered`, emit real module directories via `arch_layout_files()`.
4. **Verification**: Run `uv run --extra dev pytest -q` to execute all unit and native toolchain tests.
