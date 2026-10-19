"""B3 contract: the Rails profile must emit syntactically valid Ruby and must be
honest about what it is.

Reproduced product defect: ``config/application.rb`` interpolated the raw project
name into ``module $name``, so a legitimate hyphenated identity produced

    module my-app

which Ruby rejects outright — ``class/module name must be CONSTANT`` plus
``syntax error, unexpected '-'``. The profile now uses a stable valid module
identifier instead of the user's distribution name.

Scope honesty: the host Ruby available to this suite is 2.6.x, while the Gemfile
pins ``rails`` ``~> 7.1``, which needs Ruby >= 3.1. The assignment directs the
narrow honest option: keep Rails as an **experimental layout**, enumerate the
preparation it is missing, and never claim runnable Rails. The native checks here
are ``ruby -c`` *syntax* checks on generated files only. Syntax validity is not
runtime verification: nothing in this file boots Rails, installs a gem, or runs
``rails server``.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from bootstrapper.templates import get_template, render

RUBY = shutil.which("ruby")
NAME = "my-app"
VARS = dict(name=NAME, description="demo rails layout", year="2026", holder="acme")

ruby_required = pytest.mark.skipif(
    RUBY is None,
    reason=(
        "ruby binary not found on PATH; native syntax checks are skipped. "
        "A skipped syntax check is not a passing one, and never meant runtime proof."
    ),
)


def _rendered_files() -> dict[str, str]:
    spec = get_template("rails")
    return {render(p, **VARS): render(b, **VARS) for p, b in spec["files"].items()}


def _materialize(tmp_path) -> Path:
    root = tmp_path / "rails-proj"
    for rel, body in _rendered_files().items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body)
    return root


def _ruby_check(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run([RUBY, "-c", str(path)], capture_output=True, text=True)


# --- native: the real acceptance criteria ------------------------------------


@ruby_required
def test_hyphenated_name_still_produces_valid_ruby(tmp_path):
    """`module my-app` was the reproduced syntax error; ruby -c must now pass."""
    root = _materialize(tmp_path)
    app = root / "config/application.rb"
    res = _ruby_check(app)
    assert res.returncode == 0, res.stdout + res.stderr


@ruby_required
def test_every_generated_ruby_file_is_syntactically_valid(tmp_path):
    root = _materialize(tmp_path)
    offenders = {}
    for rb in sorted(root.rglob("*.rb")):
        res = _ruby_check(rb)
        if res.returncode != 0:
            offenders[rb.relative_to(root).as_posix()] = (res.stdout + res.stderr).strip()
    assert not offenders, offenders


@ruby_required
def test_application_defines_a_loadable_constant_module(tmp_path):
    """The generated application.rb must define a module Ruby can actually load by
    name. Asserts the *property* (a valid constant identifier) rather than any one
    chosen name, so it stays a behavior test and not an implementation mirror."""
    root = _materialize(tmp_path)
    source = (root / "config/application.rb").read_text()

    declared = re.search(r"^module\s+(\S+)\s*$", source, re.M)
    assert declared, "generated application.rb declares no module"
    const = declared.group(1)
    assert re.fullmatch(r"[A-Z]\w*", const), f"{const!r} is not a valid Ruby constant"

    # Load it for real with Rails stubbed out: this proves the identifier is
    # usable, without installing a gem or booting the framework. The stub only
    # needs to absorb `config.load_defaults`; it verifies the module/class
    # identity, not Rails behavior.
    stub = (
        "module Rails; class Application\n"
        "  def self.load_defaults(_); end\n"
        "  def self.config; @config ||= Object.new.tap { |o| def o.load_defaults(*); end }; end\n"
        "end; end\n"
    )
    probe = tmp_path / "probe.rb"
    probe.write_text(
        stub
        + source.replace('require "rails/all"', "")
        + f"\nputs defined?({const}).to_s\n"
        + f"puts ({const}::Application <= Rails::Application).to_s\n"
    )
    res = subprocess.run([RUBY, str(probe)], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    lines = res.stdout.split()
    assert lines == ["constant", "true"], res.stdout


# --- scope honesty: explicit experimental labeling ---------------------------


def test_rails_profile_is_marked_experimental():
    spec = get_template("rails")
    assert "experimental" in spec["description"].lower()


def test_generated_readme_states_experimental_scope_and_missing_preparation():
    readme = _rendered_files()["README.md"]
    lowered = readme.lower()
    assert "experimental" in lowered
    # Must not claim a runnable Rails app.
    assert "not runnable" in lowered or "does not run" in lowered or "cannot run" in lowered
    # And must enumerate what is missing rather than leave it implicit.
    for token in ("config/environment.rb", "ruby", "bundle install"):
        assert token in lowered, f"missing-preparation list omitted {token!r}"
