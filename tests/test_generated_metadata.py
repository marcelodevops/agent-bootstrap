"""A2 contract: format-safe generated metadata.

A project description is a free-text value, so ordinary content — double quotes,
a backslash, a real newline and non-ASCII text — must survive generation without
breaking the format that embeds it:

* ``pyproject.toml`` (Python) is parsed by ``tomllib``;
* ``package.json`` (TypeScript) is parsed by ``json``;
* ``Chart.yaml`` (Helm) is parsed by ``yaml``;
* ``README.md`` must still show the exact same description, human-readable and
  unchanged (no escaping leaked into prose).

Every assertion here parses a *real generated artifact* and compares the decoded
value to the input. None of them asserts that ``templates.py`` contains a
particular implementation line.
"""

import json
import tomllib

import pytest
import yaml

from bootstrapper.templates import get_template, render

# Double quotes, a single backslash, a real newline and Unicode, all at once.
TRICKY = 'A "quoted" service C:\\path\nsecond café'
# A GitHub Actions-style expression used as a *value* must survive verbatim.
ACTIONS_VALUE = 'build on ${{ matrix.os }}'

BASE = dict(name="myapp", year="2026", holder="acme", arch="modular",
            outputs_dir="outputs", scripts_dir="scripts", prompts_file="PROMPTS.md")


def _render(template_name: str, description: str) -> dict[str, str]:
    spec = get_template(template_name)
    variables = {**BASE, "description": description}
    return {p: render(b, **variables) for p, b in spec["files"].items()}


# --- each supported metadata format parses back to the exact input ----------


def test_python_pyproject_toml_preserves_description():
    rendered = _render("python-microservice", TRICKY)["pyproject.toml"]
    data = tomllib.loads(rendered)
    assert data["project"]["description"] == TRICKY


def test_typescript_package_json_preserves_description():
    rendered = _render("typescript", TRICKY)["package.json"]
    data = json.loads(rendered)
    assert data["description"] == TRICKY


def test_helm_chart_yaml_preserves_description():
    rendered = _render("helm-chart", TRICKY)["Chart.yaml"]
    data = yaml.safe_load(rendered)
    assert data["description"] == TRICKY


def test_markdown_readme_shows_description_unchanged():
    readme = _render("python-microservice", TRICKY)["README.md"]
    # Prose keeps the literal, human-readable text: no escaping, folds, or
    # dropped characters.
    assert readme == f"# {BASE['name']}\n\n{TRICKY}\n"


# --- template syntax that must NOT be touched -------------------------------


def test_helm_go_expressions_survive_render():
    files = _render("helm-chart", TRICKY)
    helpers = files["templates/_helpers.tpl"]
    deployment = files["templates/deployment.yaml"]
    assert '{{ printf "%s-%s" .Chart.Name .Chart.Version' in helpers
    assert "{{ .Values.replicaCount }}" in deployment
    assert '{{ .Values.image.tag | default .Chart.AppVersion }}' in deployment


def test_github_action_expression_survives_as_a_value():
    # An expression inside the description is data, not a template directive:
    # it must be encoded safely and decoded back verbatim in each format.
    toml = tomllib.loads(_render("python-microservice", ACTIONS_VALUE)["pyproject.toml"])
    pkg = json.loads(_render("typescript", ACTIONS_VALUE)["package.json"])
    chart = yaml.safe_load(_render("helm-chart", ACTIONS_VALUE)["Chart.yaml"])
    assert toml["project"]["description"] == ACTIONS_VALUE
    assert pkg["description"] == ACTIONS_VALUE
    assert chart["description"] == ACTIONS_VALUE


# --- composition callers emit parseable metadata ----------------------------


@pytest.mark.parametrize(
    "lang,path,key",
    [
        ("python", "pyproject.toml", ("project", "description")),
        ("typescript", "package.json", ("description",)),
        ("helm-chart", "Chart.yaml", ("description",)),
    ],
)
def test_composition_output_parses(tmp_path, lang, path, key):
    # The real composer/CLI path shares this renderer; the generated file must
    # still parse and round-trip the tricky description.
    from bootstrapper.composer import compose_project_files
    from bootstrapper.presets import resolve_preset

    preset = resolve_preset("default", agents=[], config_dir=tmp_path)
    files = compose_project_files(
        name="myapp", description=TRICKY, lang=lang, preset=preset,
        license="none", holder="acme", config_dir=tmp_path,
    )
    rendered = files[path]
    if path.endswith(".toml"):
        parsed = tomllib.loads(rendered)
    elif path.endswith(".json"):
        parsed = json.loads(rendered)
    else:
        parsed = yaml.safe_load(rendered)
    value = parsed
    for part in key:
        value = value[part]
    assert value == TRICKY
