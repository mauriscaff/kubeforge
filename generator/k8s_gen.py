"""Generates Kubernetes manifest YAML files using Jinja2 templates."""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "k8s"

_SECRET_KEYWORDS = {"password", "secret", "key", "token", "credential", "private", "auth", "api_key", "apikey"}


def _is_secret(key: str) -> bool:
    lower = key.lower()
    return any(kw in lower for kw in _SECRET_KEYWORDS)


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def generate(context: dict) -> dict[str, str]:
    """
    context keys:
      app_name, namespace, replicas, service_type, image_name, port,
      cpu_request, memory_request, cpu_limit, memory_limit,
      env_vars (list[dict] with keys 'key','value'), health_check_path

    Returns dict of {filename: content}
    """
    env = _jinja_env()

    env_list = context.get("env_vars", [])
    config_vars = {e["key"]: e.get("value", "") for e in env_list if not _is_secret(e["key"])}
    secret_vars = [e["key"] for e in env_list if _is_secret(e["key"])]

    ctx = {**context, "config_vars": config_vars, "secret_vars": secret_vars}

    files: dict[str, str] = {}
    files["deployment.yaml"] = env.get_template("deployment.j2").render(**ctx)
    files["service.yaml"] = env.get_template("service.j2").render(**ctx)

    if config_vars:
        files["configmap.yaml"] = env.get_template("configmap.j2").render(**ctx)

    if secret_vars:
        files["secret.yaml"] = env.get_template("secret.j2").render(**ctx)

    files["kustomization.yaml"] = env.get_template("kustomization.j2").render(**ctx)

    return files
