"""B1 contract: a generated Helm chart must lint and template with native helm.

Two reproduced product defects are covered:

* ``templates/_helpers.tpl`` leaked a leading newline from the ``fullname``
  helper, so ``name: {{ include "...fullname" . }}`` rendered ``name:\\nmyapp``
  and both ``helm lint`` and ``helm template`` failed with
  ``line 6: could not find expected ':'``.
* ``values.yaml`` left ``image.tag`` empty, so the container image rendered as
  ``ghcr.io/example/myapp:`` (trailing colon). The default must fall back to
  ``Chart.AppVersion`` (``1.0.0``) while an explicit ``image.tag`` still wins.

``helm template``/``helm lint`` render locally; they do NOT deploy to a cluster,
and ``ghcr.io/example/myapp`` is a placeholder image that is not verified to
exist or run. Native checks are skipped with an explicit reason when the ``helm``
binary is absent; a skipped check is not a successful native verification.
"""

import shutil
import subprocess

import pytest
import yaml

from bootstrapper.templates import get_template, render

VARS = dict(name="myapp", description="demo chart", year="2026", holder="acme")
HELM = shutil.which("helm")

helm_required = pytest.mark.skipif(
    HELM is None,
    reason=(
        "helm binary not found on PATH; native lint/template are skipped. "
        "These are native-client checks, not substitutable by static parsing."
    ),
)


def _rendered_files() -> dict[str, str]:
    spec = get_template("helm-chart")
    return {p: render(b, **VARS) for p, b in spec["files"].items()}


def _materialize(tmp_path):
    chart = tmp_path / "chart"
    for rel, body in _rendered_files().items():
        dest = chart / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body)
    return chart


def _helm_template(chart, extra=()):
    proc = subprocess.run(
        [HELM, "template", "release", str(chart), *extra],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return [d for d in yaml.safe_load_all(proc.stdout) if d]


def _doc(docs, kind):
    return next(d for d in docs if d.get("kind") == kind)


def _image(docs):
    deployment = _doc(docs, "Deployment")
    return deployment["spec"]["template"]["spec"]["containers"][0]["image"]


# --- native: the real acceptance criteria -----------------------------------


@helm_required
def test_generated_chart_lints(tmp_path):
    chart = _materialize(tmp_path)
    proc = subprocess.run(
        [HELM, "lint", str(chart)], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@helm_required
def test_generated_chart_templates(tmp_path):
    chart = _materialize(tmp_path)
    docs = _helm_template(chart)
    assert _doc(docs, "Deployment")  # valid YAML round-trips through helm


@helm_required
def test_default_image_tag_falls_back_to_appversion(tmp_path):
    chart = _materialize(tmp_path)
    assert _image(_helm_template(chart)).endswith(":1.0.0")


@helm_required
def test_explicit_image_tag_override_is_honored(tmp_path):
    chart = _materialize(tmp_path)
    docs = _helm_template(chart, ["--set", "image.tag=1.2.3"])
    assert _image(docs).endswith(":1.2.3")


@helm_required
def test_default_fullname_metadata_name_is_valid(tmp_path):
    chart = _materialize(tmp_path)
    deployment = _doc(_helm_template(chart), "Deployment")
    # No stray leading newline: the name is exactly the truncated chart name.
    assert deployment["metadata"]["name"] == "myapp"
    assert _doc(_helm_template(chart), "Service")["metadata"]["name"] == "myapp"
    assert deployment["metadata"]["labels"]["app.kubernetes.io/name"] == "myapp"


@helm_required
def test_fullname_override_metadata_name_is_valid(tmp_path):
    chart = _materialize(tmp_path)
    docs = _helm_template(chart, ["--set", "fullnameOverride=my-fancy-chart"])
    assert _doc(docs, "Deployment")["metadata"]["name"] == "my-fancy-chart"
    assert _doc(docs, "Service")["metadata"]["name"] == "my-fancy-chart"
