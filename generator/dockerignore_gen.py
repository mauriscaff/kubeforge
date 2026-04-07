"""Generates .dockerignore content by language."""

_TEMPLATES: dict[str, str] = {
    "node": """\
node_modules/
.git/
*.log
.env
.env.*
dist/
build/
coverage/
.nyc_output/
""",
    "python": """\
__pycache__/
*.pyc
*.pyo
.venv/
venv/
.env
.env.*
*.egg-info/
dist/
.pytest_cache/
""",
    "java": """\
target/
build/
.gradle/
*.class
*.jar
.git/
""",
    "go": """\
vendor/
.git/
*.exe
bin/
""",
    "dotnet": """\
bin/
obj/
.git/
*.user
.vs/
""",
}

_DEFAULT = """\
.git/
*.log
.env
.env.*
"""


def generate(language: str) -> str:
    return _TEMPLATES.get(language, _DEFAULT)
