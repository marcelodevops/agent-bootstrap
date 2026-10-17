import re

from bootstrapper.templates import LICENSES, get_template, render

VARS = dict(name="demo", description="d", year="2026", holder="acme")


def _rendered(template):
    spec = get_template(template)
    return {p: render(b, **VARS) for p, b in spec["files"].items()}


def test_helm_chart_all_includes_have_defines():
    files = _rendered("helm-chart")
    helpers = files["templates/_helpers.tpl"]
    defines = set(re.findall(r'define "([^"]+)"', helpers))
    body = helpers + files["templates/deployment.yaml"] + files["templates/service.yaml"]
    includes = set(re.findall(r'include "([^"]+)"', body))
    assert includes, "expected include references"
    missing = includes - defines
    assert not missing, f"undefined helpers: {missing}"
    # Go-template tokens must survive $name substitution intact.
    assert "{{ .Values.replicaCount }}" in files["templates/deployment.yaml"]


def test_typescript_has_compiler_and_no_lockfile_ci():
    files = _rendered("typescript")
    assert '"typescript"' in files["package.json"]
    # No committed lockfile, so Dockerfile must not use `npm ci`.
    assert "npm ci" not in files["Dockerfile"]
    assert "RUN npm install" in files["Dockerfile"]


def test_python_dockerfile_does_not_hide_install():
    files = _rendered("python-microservice")
    docker = files["Dockerfile"]
    assert "|| true" not in docker
    assert "requirements.txt" in files
    assert "COPY requirements.txt ./" in docker


def test_mit_license_is_complete():
    mit = render(LICENSES["mit"], **VARS)
    assert "Copyright (c) 2026 acme" in mit
    # Previously truncated: these closing clauses must be present.
    assert "IN NO EVENT SHALL THE" in mit
    assert "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE" in mit


def test_apache_and_gpl_are_honest_notices():
    apache = render(LICENSES["apache2"], **VARS)
    gpl = render(LICENSES["gpl3"], **VARS)
    assert "apache.org/licenses/LICENSE-2.0" in apache
    assert "gnu.org/licenses" in gpl
