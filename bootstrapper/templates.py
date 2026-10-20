"""Curated scaffold templates rendered with string.Template.

string.Template ($name, $description, $year, $holder) is chosen deliberately
over str.format()/Jinja2 because Helm's Go-template syntax (``{{ .Values.x }}``)
and GitHub Actions' ``${{ ... }}`` expressions must pass through untouched.

To emit a literal ``$`` in a template body, write ``$`` normally: string.Template
only substitutes ``$identifier`` or ``${identifier}``. GitHub Actions ``${{ ... }}``
is safe because ``{`` is not a valid identifier char. For the rare case where a
body needs a literal ``$name``-looking token, escape it as ``$$``.
"""

from __future__ import annotations

import json
import re
import unicodedata
from string import Template

# name -> {metadata, files: {path: template_body}}
TEMPLATES: dict[str, dict] = {
    "python-microservice": {
        "name": "python-microservice",
        "description": (
            "Python starter package (src layout, tests, Dockerfile, CI); "
            "a starting point, not a production microservice"
        ),
        "files": {
            "README.md": (
                "# $name\n\n"
                "$description\n\n"
                "## Quickstart\n\n"
                "```bash\n"
                "python -m venv .venv && source .venv/bin/activate\n"
                "pip install -e .\n"
                "appstarter          # installed entrypoint\n"
                "python -m appstarter\n"
                "```\n\n"
                "## Test and build\n\n"
                "```bash\n"
                "pip install pytest\n"
                "pytest\n"
                "pip install build && python -m build\n"
                "```\n\n"
                "## Layout\n\n"
                "`src/appstarter/` is the import package and keeps the name "
                "`appstarter` regardless of the project or distribution name, so "
                "`import appstarter` and the `appstarter` command stay stable even "
                "for hyphenated identities like `$name`. `__main__.py` is what makes "
                "the documented `python -m appstarter` work. `src/main.py` is a thin "
                "compatibility shim for `python src/main.py`.\n"
            ),
            ".gitignore": (
                "__pycache__/\n"
                "*.py[cod]\n"
                ".venv/\n"
                "# protect real secrets, keep every shareable template tracked\n"
                ".env\n"
                ".env.*\n"
                "!.env.example\n"
                "!.env.sample\n"
                "!.env.template\n"
                "dist/\n"
                "build/\n"
                "*.egg-info/\n"
            ),
            "pyproject.toml": (
                "[project]\n"
                'name = "$name"\n'
                'version = "0.1.0"\n'
                'description = $description_json\n'
                'requires-python = ">=3.11"\n\n'
                "[project.scripts]\n"
                'appstarter = "appstarter.main:main"\n\n'
                "[build-system]\n"
                'requires = ["setuptools>=61"]\n'
                'build-backend = "setuptools.build_meta"\n\n'
                "[tool.setuptools]\n"
                'packages = ["appstarter"]\n\n'
                "[tool.setuptools.package-dir]\n"
                '"" = "src"\n\n'
                "[tool.pytest.ini_options]\n"
                'testpaths = ["tests"]\n'
                'pythonpath = ["src"]\n'
            ),
            "src/appstarter/__init__.py": (
                '"""Stable import package for $name."""\n\n'
                'from appstarter.main import main\n\n'
                '__all__ = ["main"]\n'
            ),
            "src/appstarter/main.py": (
                '"""Entry point for $name."""\n\n\n'
                "def main() -> None:\n"
                "    print('Hello from $name!')\n\n\n"
                'if __name__ == "__main__":\n'
                "    main()\n"
            ),
            # Without this module `python -m appstarter` fails with
            # "No module named appstarter.__main__", so the README would document
            # a command the built artifact does not support.
            "src/appstarter/__main__.py": (
                '"""Module entry point for `python -m appstarter`."""\n\n'
                "from appstarter.main import main\n\n"
                'if __name__ == "__main__":\n'
                "    main()\n"
            ),
            # Compatibility shim: `python src/main.py` keeps working for existing
            # invocations, but the package above is the real, installable module.
            "src/main.py": (
                '"""Compatibility shim; the package lives in src/appstarter/."""\n\n'
                "from appstarter.main import main\n\n"
                'if __name__ == "__main__":\n'
                "    main()\n"
            ),
            "tests/test_appstarter.py": (
                "from appstarter import main\n"
                "from appstarter.main import main as entry\n\n\n"
                "def test_main_runs(capsys):\n"
                "    main()\n"
                "    assert 'Hello from $name!' in capsys.readouterr().out\n\n\n"
                "def test_entry_point_is_importable():\n"
                "    assert entry is main\n"
            ),
            ".env.example": (
                "# Copy to .env and fill in real values. .env itself is ignored.\n"
                "APP_NAME=$name\n"
            ),
            "requirements.txt": (
                "# Runtime dependencies, one per line (pip install -r requirements.txt).\n"
                "# The project itself is installed with `pip install .` (see pyproject.toml).\n"
            ),
            "Dockerfile": (
                "FROM python:3.11-slim\n"
                "WORKDIR /app\n"
                "COPY requirements.txt ./\n"
                "RUN pip install --no-cache-dir -r requirements.txt\n"
                "COPY . .\n"
                "RUN pip install .\n"
                'CMD ["appstarter"]\n'
            ),
            ".github/workflows/ci.yml": (
                "name: CI\n"
                "on: [push]\n"
                "jobs:\n"
                "  build:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - uses: actions/checkout@v4\n"
                "      - uses: actions/setup-python@v5\n"
                "        with:\n"
                "          python-version: '3.11'\n"
                "      - run: pip install . pytest\n"
                "      - run: pytest\n"
                "      - run: pip install build && python -m build\n"
            ),
        },
    },
    "helm-chart": {
        "name": "helm-chart",
        "description": "Helm chart scaffold (Chart.yaml, values, templates, lint CI)",
        "files": {
            "Chart.yaml": (
                'apiVersion: v2\n'
                'name: $helm_name\n'
                'description: $description_json\n'
                'type: application\n'
                'version: 0.1.0\n'
                'appVersion: "1.0.0"\n'
            ),
            "values.yaml": (
                "replicaCount: 1\n"
                "nameOverride: \"\"\n"
                "fullnameOverride: \"\"\n"
                "image:\n"
                "  repository: ghcr.io/example/$name\n"
                "  tag: \"\"\n"
                "  pullPolicy: IfNotPresent\n"
                "service:\n"
                "  type: ClusterIP\n"
                "  port: 80\n"
            ),
            ".helmignore": "logs/\n*.tfvars\n",
            "templates/_helpers.tpl": (
                '{{- define "$name.chart" -}}\n'
                '{{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}\n'
                "{{- end }}\n\n"
                '{{- define "$name.name" -}}\n'
                "{{ default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix \"-\" }}\n"
                "{{- end }}\n\n"
                '{{- define "$name.fullname" -}}\n'
                "{{- if .Values.fullnameOverride }}\n"
                '{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}\n'
                "{{- else }}\n"
                '{{- printf "%s" .Chart.Name | trunc 63 | trimSuffix "-" }}\n'
                "{{- end }}\n"
                "{{- end }}\n\n"
                '{{- define "$name.selectorLabels" -}}\n'
                "app.kubernetes.io/name: {{ include \"$name.name\" . }}\n"
                "app.kubernetes.io/instance: {{ .Release.Name }}\n"
                "{{- end }}\n\n"
                '{{- define "$name.labels" -}}\n'
                "helm.sh/chart: {{ include \"$name.chart\" . }}\n"
                "{{ include \"$name.selectorLabels\" . }}\n"
                "{{- if .Chart.AppVersion }}\n"
                "app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}\n"
                "{{- end }}\n"
                "app.kubernetes.io/managed-by: {{ .Release.Service }}\n"
                "{{- end }}\n"
            ),
            "templates/deployment.yaml": (
                "apiVersion: apps/v1\n"
                "kind: Deployment\n"
                "metadata:\n"
                "  name: {{ include \"$name.fullname\" . }}\n"
                "  labels:\n"
                "    {{- include \"$name.labels\" . | nindent 4 }}\n"
                "spec:\n"
                "  replicas: {{ .Values.replicaCount }}\n"
                "  selector:\n"
                "    matchLabels:\n"
                "      {{- include \"$name.selectorLabels\" . | nindent 6 }}\n"
                "  template:\n"
                "    metadata:\n"
                "      labels:\n"
                "        {{- include \"$name.selectorLabels\" . | nindent 8 }}\n"
                "    spec:\n"
                "      containers:\n"
                "        - name: $name\n"
                "          image: \"{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}\"\n"
            ),
            "templates/service.yaml": (
                "apiVersion: v1\n"
                "kind: Service\n"
                "metadata:\n"
                "  name: {{ include \"$name.fullname\" . }}\n"
                "spec:\n"
                "  type: {{ .Values.service.type }}\n"
                "  ports:\n"
                "    - port: {{ .Values.service.port }}\n"
                "  selector:\n"
                "    {{- include \"$name.selectorLabels\" . | nindent 4 }}\n"
            ),
            ".github/workflows/helm-lint.yml": (
                "name: Helm Lint\n"
                "on: [push]\n"
                "jobs:\n"
                "  lint:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - uses: actions/checkout@v4\n"
                "      - name: Set up Helm\n"
                "        uses: azure/setup-helm@v4\n"
                "      - run: helm lint .\n"
                "      - run: helm template $name .\n"
            ),
        },
    },
    "rails": {
        "name": "rails",
        "description": (
            "EXPERIMENTAL Rails-style layout only (not runnable, not `rails new` output)"
        ),
        "files": {
            "README.md": (
                "# $name\n\n"
                "$description\n\n"
                "## Status: experimental layout, not a runnable Rails app\n\n"
                "This profile is a partial directory sketch. It does **not** run: "
                "`config.ru` boots via `rails server` only after the missing files "
                "below exist, and this skeleton was never executed or verified as a "
                "bootable Rails application.\n\n"
                "### Missing preparation\n\n"
                "- `config/environment.rb` (required by `config.ru`) and "
                "`config/boot.rb`, `config/routes.rb`\n"
                "- `bin/rails`, `Rakefile`, `app/views/`, `db/`\n"
                "- Ruby >= 3.1 for `rails` `~> 7.1` (older system Ruby cannot run it)\n"
                "- `bundle install` for the Gemfile dependencies\n\n"
                "To get a verified Rails app, run `rails new` with a supported Ruby "
                "instead of relying on this layout.\n"
            ),
            "Gemfile": (
                "source \"https://rubygems.org\"\n"
                "gem \"rails\", \"~> 7.1\"\n"
                "gem \"puma\"\n"
            ),
            "config.ru": (
                "require_relative \"config/environment\"\n"
                "run Rails.application\n"
                "Rails.application.load_server\n"
            ),
            "config/application.rb": (
                "require \"rails/all\"\n\n"
                "# Stable module identifier. It must be a Ruby CONSTANT, so the\n"
                "# project name is not interpolated here: a hyphenated identity\n"
                "# such as \"$name\" is invalid as a module name and broke\n"
                "# `ruby -c`. Rename deliberately if you regenerate this app.\n"
                "module AppStarter\n"
                "  class Application < Rails::Application\n"
                "    config.load_defaults 7.1\n"
                "  end\n"
                "end\n"
            ),
            "app/controllers/application_controller.rb": (
                "class ApplicationController < ActionController::Base\n"
                "end\n"
            ),
        },
    },
    "typescript": {
        "name": "typescript",
        "description": "TypeScript service with package.json, tsconfig, multi-stage Dockerfile",
        "files": {
            "README.md": "# $name\n\n$description\n",
            ".gitignore": "node_modules/\ndist/\n",
            "package.json": (
                "{\n"
                "  \"name\": \"$name\",\n"
                "  \"version\": \"0.1.0\",\n"
                "  \"description\": $description_json,\n"
                "  \"scripts\": {\n"
                "    \"build\": \"tsc\",\n"
                "    \"start\": \"node dist/index.js\"\n"
                "  },\n"
                "  \"devDependencies\": {\n"
                "    \"typescript\": \"^5.4.0\",\n"
                "    \"@types/node\": \"^20.11.0\"\n"
                "  }\n"
                "}\n"
            ),
            "tsconfig.json": (
                "{\n"
                "  \"compilerOptions\": {\n"
                "    \"target\": \"ES2022\",\n"
                "    \"module\": \"nodenext\",\n"
                "    \"moduleResolution\": \"nodenext\",\n"
                "    \"outDir\": \"dist\",\n"
                "    \"rootDir\": \"src\",\n"
                "    \"strict\": true\n"
                "  },\n"
                "  \"include\": [\"src\"]\n"
                "}\n"
            ),
            "src/index.ts": (
                "export function main(): void {\n"
                "  console.log('Hello from $name!');\n"
                "}\n\n"
                "main();\n"
            ),
            "Dockerfile": (
                "FROM node:20-alpine AS build\n"
                "WORKDIR /app\n"
                "COPY package*.json ./\n"
                "RUN npm install\n"
                "COPY . .\n"
                "RUN npm run build\n\n"
                "FROM node:20-alpine\n"
                "WORKDIR /app\n"
                "COPY --from=build /app/dist ./dist\n"
                "COPY --from=build /app/package*.json ./\n"
                "RUN npm install --omit=dev\n"
                'CMD ["node", "dist/index.js"]\n'
            ),
        },
    },
    "none": {
        "name": "none",
        "description": "Minimal agent-only repository (README and .gitignore only)",
        "files": {
            "README.md": "# $name\n\n$description\n",
            ".gitignore": ".env\n.venv/\n__pycache__/\n*.py[cod]\n",
        },
    },
}

TEMPLATE_ALIASES: dict[str, str] = {
    "python": "python-microservice",
}

LICENSES: dict[str, str] = {
    "mit": (
        "MIT License\n\n"
        "Copyright (c) $year $holder\n\n"
        "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
        "of this software and associated documentation files (the \"Software\"), to deal\n"
        "in the Software without restriction, including without limitation the rights\n"
        "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
        "copies of the Software, and to permit persons to whom the Software is\n"
        "furnished to do so, subject to the following conditions:\n\n"
        "The above copyright notice and this permission notice shall be included in all\n"
        "copies or substantial portions of the Software.\n\n"
        "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n"
        "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n"
        "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n"
        "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n"
        "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n"
        "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n"
        "SOFTWARE.\n"
    ),
    "apache2": (
        "Copyright $year $holder\n\n"
        "Licensed under the Apache License, Version 2.0 (the \"License\");\n"
        "you may not use this file except in compliance with the License.\n"
        "You may obtain a copy of the License at\n\n"
        "    http://www.apache.org/licenses/LICENSE-2.0\n\n"
        "Unless required by applicable law or agreed to in writing, software\n"
        "distributed under the License is distributed on an \"AS IS\" BASIS,\n"
        "WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n"
        "See the License for the specific language governing permissions and\n"
        "limitations under the License.\n"
    ),
    "gpl3": (
        "Copyright (C) $year $holder\n\n"
        "This program is free software: you can redistribute it and/or modify\n"
        "it under the terms of the GNU General Public License as published by\n"
        "the Free Software Foundation, either version 3 of the License, or\n"
        "(at your option) any later version.\n\n"
        "This program is distributed in the hope that it will be useful,\n"
        "but WITHOUT ANY WARRANTY; without even the implied warranty of\n"
        "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n"
        "GNU General Public License for more details.\n\n"
        "You should have received a copy of the GNU General Public License\n"
        "along with this program.  If not, see <https://www.gnu.org/licenses/>.\n"
    ),
}


def render(text: str, **variables: str) -> str:
    """Render a template body. Undefined ``$tokens`` are left untouched.

    A ``$description_json`` token is derived from ``description`` using the
    stdlib ``json`` encoder. Structured formats (``pyproject.toml``,
    ``package.json``, ``Chart.yaml``) interpolate that token so a description
    with quotes, backslashes, newlines or non-ASCII text becomes a single valid,
    decodable string literal; the surrounding quotes come from the encoder, so
    those templates must not add their own. ``$description`` itself stays the
    raw, human-readable value for Markdown and agent prose.

    This is format-aware stdlib serialization, not a bespoke escaping framework:
    a JSON string literal is also a valid TOML basic string and a valid YAML
    double-quoted scalar, so one encoded token covers all three structured
    targets at runtime without importing PyYAML.
    """
    if isinstance(variables.get("name"), str):
        normalized = unicodedata.normalize("NFKD", variables["name"])
        ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
        helm_name = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-") or "chart"
        variables = {**variables, "helm_name": helm_name}
    if isinstance(variables.get("description"), str):
        variables = {
            **variables,
            "description_json": json.dumps(variables["description"], ensure_ascii=False),
        }
    return Template(text).safe_substitute(**variables)


def template_names() -> list[str]:
    return sorted(TEMPLATES)


def get_template(name: str) -> dict:
    resolved = TEMPLATE_ALIASES.get(name, name)
    if resolved not in TEMPLATES:
        raise KeyError(
            f"Unknown template '{name}'. Available: {', '.join(template_names())}"
        )
    return TEMPLATES[resolved]

