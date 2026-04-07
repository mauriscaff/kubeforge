"""Generates Dockerfile content using Jinja2 templates."""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _env(language: str) -> Environment:
    template_dir = TEMPLATES_DIR / language
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # Custom filter: split string into list
    env.filters["split"] = lambda s: s.split()
    return env


def generate(context: dict) -> str:
    """
    context keys:
      language, framework, base_image, build_image, port, user,
      start_command, build_command, has_build_step, package_manager, build_tool
    """
    language = context["language"]
    has_build_step = context.get("has_build_step", False)

    if language == "node":
        template_name = "dockerfile_build.j2" if has_build_step else "dockerfile_simple.j2"
    else:
        template_name = "dockerfile.j2"

    jinja_env = _env(language)
    template = jinja_env.get_template(template_name)
    return template.render(**context)
