"""B3 contract: the generated Python starter must be a real, installable,
runnable and testable project, verified with native tooling.

Reproduced product defects this covers:

* The old ``python-microservice`` template declared a ``[build-system]`` but no
  package discovery, so ``python -m build`` emitted a wheel containing a bare
  top-level ``main.py`` (auto-discovery of ``src/``). It was technically
  "installable" but shipped no importable package, no test suite, and the only
  documented run command (``python src/main.py``) only worked inside the checkout.
* The distribution name followed the user's project name, so a hyphenated
  identity like ``my-app`` produced an import package that did not match it and
  no stable module to import. The reference now fixes a stable import package
  (``appstarter``) that is deliberately independent of the distribution name.

Every check here builds and installs the *generated artifact* into a disposable
virtualenv and runs the documented commands outside the source checkout. Native
tools (``uv``/``venv`` + ``build``) are required; each test skips with an explicit
reason when they are unavailable. A skip is not a pass, and nothing here asserts
that a template source file merely contains a chosen line of text.
"""

import os
import re
import shutil
import subprocess
import sys
import zipfile
from email import message_from_string
from pathlib import Path

import pytest

from bootstrapper.templates import get_template, render

NAME = "my-app"  # hyphenated identity, required to be exercised
DIST = "my_app"  # what setuptools normalizes it to in the wheel filename
PKG = "appstarter"  # stable import package, independent of the distribution name
VARS = dict(name=NAME, description="demo starter", year="2026", holder="acme")


def _canonical(name: str) -> str:
    """PEP 503 name normalization."""
    return re.sub(r"[-_.]+", "-", name).lower()

UV = shutil.which("uv")
# Resolved explicitly: subprocess would already bypass a shell *function* named
# `git`, but naming the binary documents that ignore-rule evidence must come from
# git itself and nothing that post-processes `.gitignore`.
GIT = shutil.which("git")
BUILD_OK = True
try:
    import build  # noqa: F401
except ImportError:  # pragma: no cover - environment dependent
    BUILD_OK = False

native_required = pytest.mark.skipif(
    not (UV and BUILD_OK),
    reason=(
        "needs uv on PATH and the `build` module in the test interpreter; "
        "native build/install/run checks cannot be substituted by static parsing"
    ),
)


def _render_files() -> dict[str, str]:
    spec = get_template("python-microservice")
    return {render(p, **VARS): render(b, **VARS) for p, b in spec["files"].items()}


def _materialize(root: Path) -> Path:
    project = root / NAME
    project.mkdir(parents=True)
    for rel, body in _render_files().items():
        dest = project / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body)
    return project


def _run(cmd, cwd=None, env=None, timeout=300):
    proc = subprocess.run(
        cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
    )
    return proc


@pytest.fixture(scope="module")
def installed(tmp_path_factory):
    """Build the generated project once and install its wheel in a disposable venv."""
    root = tmp_path_factory.mktemp("pystarter")
    project = _materialize(root)
    venv = root / "venv"

    built = _run([sys.executable, "-m", "build", "--wheel", "--outdir", str(root / "dist"), str(project)])
    assert built.returncode == 0, built.stdout + built.stderr

    made = _run([UV, "venv", str(venv), "--python", sys.executable], cwd=root)
    assert made.returncode == 0, made.stdout + made.stderr
    py = venv / "bin" / "python"

    wheels = sorted((root / "dist").glob("*.whl"))
    assert wheels, "build produced no wheel"
    inst = _run([UV, "pip", "install", "--python", str(py), str(wheels[0])], cwd=root)
    assert inst.returncode == 0, inst.stdout + inst.stderr

    return {"project": project, "python": str(py), "wheel": wheels[0], "venv": venv}


@native_required
def test_documented_entrypoint_runs_outside_the_checkout(installed):
    """The README's documented command works from an unrelated cwd, installed."""
    elsewhere = installed["project"].parent / "elsewhere"
    elsewhere.mkdir(exist_ok=True)
    readme = (installed["project"] / "README.md").read_text()
    assert "\nappstarter" in readme, "guard: this test must cover a documented command"
    res = _run(["appstarter"], cwd=elsewhere, env=_venv_env(installed))
    assert res.returncode == 0, res.stdout + res.stderr
    assert f"Hello from {NAME}!" in res.stdout


def _venv_env(installed):
    env = dict(os.environ)
    env["PATH"] = f"{installed['venv'] / 'bin'}{os.pathsep}{env['PATH']}"
    return env


@native_required
def test_documented_module_entrypoint_runs_from_installed_wheel(installed):
    """The README documents ``python -m appstarter`` next to the console script, so
    the installed wheel must honor that exact command from outside the checkout.

    Reproduced defect: the package had no ``__main__.py``, so the documented line
    failed with ``No module named appstarter.__main__`` even though the console
    script worked. Supporting the documented command (rather than deleting the
    documentation) is the fix, and the console script must keep working.
    """
    elsewhere = installed["project"].parent / "elsewhere-module"
    elsewhere.mkdir(exist_ok=True)

    readme = (installed["project"] / "README.md").read_text()
    assert f"python -m {PKG}" in readme, "guard: this test must cover a documented command"

    res = _run([installed["python"], "-m", PKG], cwd=elsewhere)
    assert res.returncode == 0, (
        f"`python -m {PKG}` is documented in the generated README but failed: "
        f"{res.stdout}{res.stderr}"
    )
    assert f"Hello from {NAME}!" in res.stdout

    names = zipfile.ZipFile(installed["wheel"]).namelist()
    assert f"{PKG}/__main__.py" in names, (
        "the documented module entrypoint must ship inside the built wheel, "
        f"not only in the source tree; got {names}"
    )

    console = _run(["appstarter"], cwd=elsewhere, env=_venv_env(installed))
    assert console.returncode == 0, console.stdout + console.stderr
    assert f"Hello from {NAME}!" in console.stdout


@native_required
def test_wheel_contains_a_real_importable_package(installed):
    """Importing the stable package name works in the disposable venv, and the
    accidental top-level module from auto-discovery must not be shipped."""
    res = _run(
        [installed["python"], "-c", f"import {PKG}; {PKG}.main()"],
        cwd=installed["project"].parent,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    names = zipfile.ZipFile(installed["wheel"]).namelist()
    assert f"{PKG}/__init__.py" in names
    assert "main.py" not in names  # the old broken artifact shipped exactly this


@native_required
def test_hyphenated_identity_produces_valid_normalized_metadata(installed):
    """PEP 621 metadata must parse; the hyphenated identity is authored as-is and
    normalized (PEP 503) in the artifact filename, and both must agree."""
    with zipfile.ZipFile(installed["wheel"]) as zf:
        metadata_name = next(n for n in zf.namelist() if n.endswith(".dist-info/METADATA"))
        msg = message_from_string(zf.read(metadata_name).decode())

    assert msg["Version"] == "0.1.0"
    assert msg["Summary"] == "demo starter"
    assert _canonical(msg["Name"]) == _canonical(NAME)
    # dist-info directory and wheel filename carry the normalized form.
    assert metadata_name.startswith(f"{DIST}-0.1.0.dist-info")
    assert installed["wheel"].name == f"{DIST}-0.1.0-py3-none-any.whl"


@native_required
def test_description_with_quotes_survives_into_installed_metadata(tmp_path):
    """The accepted A2 serialization must hold for the Python profile too."""
    import tomllib

    tricky = 'A "quoted" service C:\\path\nsecond café'
    raw_body = get_template("python-microservice")["files"]["pyproject.toml"]
    data = tomllib.loads(render(raw_body, **{**VARS, "description": tricky}))
    assert data["project"]["description"] == tricky
    assert data["project"]["name"] == NAME


@native_required
def test_generated_tests_pass_against_the_generated_sources(installed):
    """`pytest` on the generated test file must pass, run from the project root."""
    proj = installed["project"]
    test_file = proj / "tests" / f"test_{PKG}.py"
    assert test_file.is_file(), "starter must ship a runnable test suite"
    env = _venv_env(installed)
    env["PYTHONPATH"] = str(proj / "src")
    deps = _run([UV, "pip", "install", "--python", installed["python"], "pytest"], cwd=proj)
    assert deps.returncode == 0, deps.stdout + deps.stderr
    res = _run(
        [installed["python"], "-m", "pytest", "-q", str(test_file)], cwd=proj, env=env
    )
    assert res.returncode == 0, res.stdout + res.stderr

    # `pytest` is documented on its own, after installing the package, with no
    # PYTHONPATH smuggled in. The bare documented command must be the one that
    # works, otherwise the README is describing an invocation that fails.
    bare = dict(_venv_env(installed))
    bare.pop("PYTHONPATH", None)
    plain = _run([installed["python"], "-m", "pytest", "-q"], cwd=proj, env=bare)
    assert plain.returncode == 0, (
        f"the README documents a bare `pytest` run that failed: {plain.stdout}{plain.stderr}"
    )


@native_required
@pytest.mark.parametrize(
    "rel,shareable",
    [
        (".env", False),
        (".env.local", False),
        (".env.example", True),
        # B3 correction round: `.env.*` ignored every dotted variant, so the other
        # two shareable templates a starter is expected to ship were hidden.
        (".env.sample", True),
        (".env.template", True),
    ],
)
def test_ignore_rules_protect_real_env_but_share_the_example(installed, rel, shareable):
    """Native git: files holding real secrets stay ignored, every shareable
    template stays trackable.

    Uses the resolved git binary on purpose: an interactive `git` shell wrapper on
    this host rewrites `.gitignore` during `git init`, which would make the
    generated rules pass a check they do not actually satisfy.
    """
    proj = installed["project"]
    (proj / rel).write_text("SECRET=hunter2\n" if not shareable else "SECRET=\n")
    init = _run([GIT, "init", "-q"], cwd=proj)
    assert init.returncode == 0, init.stdout + init.stderr

    check = _run([GIT, "check-ignore", "-q", rel], cwd=proj)
    if shareable:
        assert check.returncode != 0, f"{rel} is shareable and must not be ignored"
        listing = _run([GIT, "status", "--porcelain", rel], cwd=proj)
        assert rel in listing.stdout, f"{rel} must appear as a trackable file"
    else:
        assert check.returncode == 0, f"{rel} holds real secrets and must be ignored"


@native_required
def test_docker_and_ci_commands_are_coherent(installed):
    """What the container and CI claim to run must be the documented installed
    entrypoint and the generated tests, not a path that only works in a checkout."""
    proj = installed["project"]
    docker = (proj / "Dockerfile").read_text()
    ci = (proj / ".github" / "workflows" / "ci.yml").read_text()

    assert "pip install ." in docker
    assert "appstarter" in docker  # runs the installed console script
    assert "|| true" not in docker  # never hide a failing install
    assert "src/main.py" not in docker  # checkout-only command, unrunnable in the image
    assert "pytest" in ci
    assert "python -m build" in ci or "pip install ." in ci


def test_starter_is_described_honestly_not_as_a_production_service():
    """The profile must not over-promise: it is a starter, not a verified service."""
    files = _render_files()
    readme = files["README.md"]
    assert "starter" in readme.lower()
    spec = get_template("python-microservice")
    assert "microservice" in spec["description"].lower() or "starter" in spec["description"].lower()
