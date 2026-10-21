# Project Memory (agent-bootstrap)

Persistent context and facts for AI agents working in `agent-bootstrap` (`projboot`).

## Key Conventions
- Package source lives in `bootstrapper/`; tests live in `tests/`.
- Templates use `string.Template` (`$name`, `$pkg_name`, `$helm_name`, `$description`, `$description_json`, `$year`, `$holder`, `$arch`, `$outputs_dir`, `$scripts_dir`, `$prompts_file`) so Go templates (`{{ ... }}`) and GitHub Actions (`${{ ... }}`) pass through untouched.
- Subprocess git hooks set `GIT_TERMINAL_PROMPT=0` so non-interactive runs and tests never hang on credential prompts.
