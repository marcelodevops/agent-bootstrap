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

from string import Template

# name -> {metadata, files: {path: template_body}}
TEMPLATES: dict[str, dict] = {
    "python-microservice": {
        "name": "python-microservice",
        "description": "Python service with Dockerfile, CI, and src layout",
        "files": {
            "README.md": "# $name\n\n$description\n",
            ".gitignore": "__pycache__/\n*.py[cod]\n.env\n.venv/\n",
            "pyproject.toml": (
                "[project]\n"
                'name = "$name"\n'
                'version = "0.1.0"\n'
                'description = "$description"\n'
                'requires-python = ">=3.11"\n\n'
                "[build-system]\n"
                'requires = ["setuptools>=61"]\n'
                'build-backend = "setuptools.build_meta"\n'
            ),
            "src/main.py": (
                '"""$name entrypoint."""\n\n\n'
                "def main() -> None:\n"
                "    print('Hello from $name!')\n\n\n"
                'if __name__ == "__main__":\n'
                "    main()\n"
            ),
            "Dockerfile": (
                "FROM python:3.11-slim\n"
                "WORKDIR /app\n"
                "COPY . .\n"
                "RUN pip install -r requirements.txt || true\n"
                'CMD ["python", "src/main.py"]\n'
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
                "      - run: python src/main.py\n"
            ),
        },
    },
    "helm-chart": {
        "name": "helm-chart",
        "description": "Helm chart scaffold (Chart.yaml, values, templates, lint CI)",
        "files": {
            "Chart.yaml": (
                'apiVersion: v2\n'
                'name: $name\n'
                'description: $description\n'
                'type: application\n'
                'version: 0.1.0\n'
                'appVersion: "1.0.0"\n'
            ),
            "values.yaml": (
                "replicaCount: 1\n"
                "image:\n"
                "  repository: ghcr.io/example/$name\n"
                "  tag: \"\"\n"
                "  pullPolicy: IfNotPresent\n"
                "service:\n"
                "  type: ClusterIP\n"
                "  port: 80\n"
            ),
            ".helmignore": "logs/\n*.tfvars\n",
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
                "          image: \"{{ .Values.image.repository }}:{{ .Values.image.tag }}\"\n"
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
        "description": "Minimal Rails-style skeleton (base layout, not `rails new` output)",
        "files": {
            "README.md": "# $name\n\n$description\n",
            "Gemfile": (
                "source \"https://rubygems.org\"\n"
                "gem \"rails\", \"~> 7.1\"\n"
                "gem \"puma\"\n"
            ),
            "config.ru": (
                "require_relative \"config/environment\"\n"
                "run Rails.application\n"
            ),
            "config/application.rb": (
                "require \"rails/all\"\n\n"
                "module $name\n"
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
            "package.json": (
                "{\n"
                "  \"name\": \"$name\",\n"
                "  \"version\": \"0.1.0\",\n"
                "  \"description\": \"$description\",\n"
                "  \"scripts\": {\n"
                "    \"build\": \"tsc\",\n"
                "    \"start\": \"node dist/index.js\"\n"
                "  }\n"
                "}\n"
            ),
            "tsconfig.json": (
                "{\n"
                "  \"compilerOptions\": {\n"
                "    \"target\": \"ES2022\",\n"
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
                "RUN npm ci\n"
                "COPY . .\n"
                "RUN npm run build\n\n"
                "FROM node:20-alpine\n"
                "WORKDIR /app\n"
                "COPY --from=build /app/dist ./dist\n"
                "COPY --from=build /app/package*.json ./\n"
                "RUN npm ci --omit=dev\n"
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
        "Permission is hereby granted, free of charge, to any person obtaining a copy "
        "of this software and associated documentation files (the \"Software\"), to deal "
        "in the Software without restriction, including without limitation the rights to "
        "use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of "
        "the Software, and to permit persons to whom the Software is furnished to do so, "
        "subject to the following conditions:\n\n"
        "The above copyright notice and this permission notice shall be included in all "
        "copies or substantial portions of the Software.\n\n"
        "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND.\n"
    ),
    "apache2": (
        "                                 Apache License\n"
        "                           Version 2.0, January 2004\n\n"
        "   Copyright $year $holder\n\n"
        "   Licensed under the Apache License, Version 2.0 (the \"License\"); "
        "you may not use this file except in compliance with the License.\n"
    ),
    "gpl3": (
        "                    GNU GENERAL PUBLIC LICENSE\n"
        "                       Version 3, 29 June 2007\n\n"
        "   Copyright (C) $year $holder\n"
    ),
}


def render(text: str, **variables: str) -> str:
    """Render a template body. Undefined ``$tokens`` are left untouched."""
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

