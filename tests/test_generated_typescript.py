"""B2 contract: a generated TypeScript starter must install, build and run.

Reproduces the real defect: with the original ``tsconfig.json`` (no ``module`` /
``moduleResolution``), ``npm run build`` failed with
``error TS2792: Cannot find module 'undici-types'`` while ``npm start`` printed a
``MODULE_TYPELESS_PACKAGE_JSON`` warning because the emitted module format did not
match the package. The fix is a coherent Node module configuration, validated by
actually running the toolchain — not by asserting the template's source text.

These are native ``npm`` checks. They are skipped with an explicit reason when the
``npm`` binary is unavailable; a skip is not a pass and static parsing cannot
substitute for the real build. Network access is used only to install the
generated project's own dependencies inside a disposable temp directory; nothing
is installed globally and no host tool is changed.
"""

import json
import shutil
import subprocess

import pytest

from bootstrapper.templates import get_template, render

NPM = shutil.which("npm")
NAME = "tsstarter"
VARS = dict(
    name=NAME,
    description="starter",
    year="2026",
    holder="acme",
    arch="modular",
    outputs_dir="outputs",
    scripts_dir="scripts",
    prompts_file="PROMPTS.md",
)

npm_required = pytest.mark.skipif(
    NPM is None,
    reason=(
        "npm binary not found on PATH; the native install/build/run checks are "
        "skipped. These run the real toolchain and are not substitutable by "
        "static parsing."
    ),
)


def _materialize(dest_dir):
    app = dest_dir / "app"
    for rel, body in get_template("typescript")["files"].items():
        target = app / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render(body, **VARS))
    return app


def _npm(app, args, timeout):
    return subprocess.run(
        [NPM, *args],
        cwd=app,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@npm_required
def test_generated_typescript_starter_installs_builds_and_runs(tmp_path):
    app = _materialize(tmp_path)

    install = _npm(app, ["install", "--no-audit", "--no-fund"], timeout=600)
    assert install.returncode == 0, install.stdout + install.stderr

    build = _npm(app, ["run", "build"], timeout=300)
    assert build.returncode == 0, build.stdout + build.stderr

    start = _npm(app, ["start"], timeout=120)
    assert start.returncode == 0, start.stdout + start.stderr
    # The build produced a real artifact and it prints the expected starter line.
    assert (app / "dist" / "index.js").is_file()
    assert f"Hello from {NAME}!" in start.stdout
    # A coherent module config does not force Node to re-parse the output.
    combined = start.stdout + start.stderr
    assert "MODULE_TYPELESS_PACKAGE_JSON" not in combined


@npm_required
def test_generated_typescript_metadata_stays_valid_json(tmp_path):
    # The generated package.json is parseable JSON (the description serialization
    # and the fixed config coexist without corrupting the file).
    app = _materialize(tmp_path)
    package = json.loads((app / "package.json").read_text())
    assert package["scripts"]["build"] == "tsc"
    assert package["scripts"]["start"] == "node dist/index.js"


def test_generated_starter_ignores_node_modules_and_dist(tmp_path):
    # A real generated ignore artifact, not a template-source mirror.
    app = _materialize(tmp_path)
    gitignore = app / ".gitignore"
    assert gitignore.is_file(), "TypeScript starter must ship a .gitignore"
    entries = {line.strip() for line in gitignore.read_text().splitlines()}
    assert "node_modules/" in entries
    assert "dist/" in entries
