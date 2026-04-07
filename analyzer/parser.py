"""Extracts port, start command, and environment variables from the project."""

import json
import os
import re
from pathlib import Path


def parse(project_path: str, language: str, framework: str) -> dict:
    """
    Returns dict with: port, start_command, env_vars (list of keys)
    """
    root = Path(project_path)

    port = _detect_port(root, language, framework)
    start_command = _detect_start_command(root, language, framework)
    env_vars = _detect_env_vars(root)

    return {
        "port": port,
        "start_command": start_command,
        "env_vars": env_vars,
    }


def _detect_port(root: Path, language: str, framework: str) -> int:
    from analyzer.rules import LANGUAGE_DEFAULTS, FRAMEWORK_OVERRIDES

    # 1. Check for existing Dockerfile
    dockerfile = root / "Dockerfile"
    if dockerfile.exists():
        content = dockerfile.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"EXPOSE\s+(\d+)", content)
        if m:
            return int(m.group(1))

    # 2. package.json scripts
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
            for v in scripts.values():
                m = re.search(r"--port[=\s]+(\d+)|-p\s+(\d+)|PORT[=\s]+(\d+)", str(v))
                if m:
                    return int(next(g for g in m.groups() if g))
        except Exception:
            pass

    # 3. application.properties / application.yml
    for props_file in [root / "src/main/resources/application.properties",
                        root / "src/main/resources/application.yml"]:
        if props_file.exists():
            content = props_file.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"server\.port[:\s=]+(\d+)", content)
            if m:
                return int(m.group(1))

    # 4. .env.example / .env
    for env_file in [root / ".env.example", root / ".env"]:
        if env_file.exists():
            content = env_file.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"^PORT\s*=\s*(\d+)", content, re.MULTILINE)
            if m:
                return int(m.group(1))

    # 5. docker-compose.yml
    for compose_file in [root / "docker-compose.yml", root / "docker-compose.yaml"]:
        if compose_file.exists():
            content = compose_file.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"(\d{4,5}):\d{4,5}", content)
            if m:
                return int(m.group(1))

    # Fallback: framework/language defaults
    fw_override = FRAMEWORK_OVERRIDES.get(framework, {})
    if "port" in fw_override:
        return fw_override["port"]
    return LANGUAGE_DEFAULTS.get(language, {}).get("port", 8080)


def _detect_start_command(root: Path, language: str, framework: str) -> str:
    from analyzer.rules import LANGUAGE_DEFAULTS, FRAMEWORK_OVERRIDES

    fw_override = FRAMEWORK_OVERRIDES.get(framework, {})
    if "start_command" in fw_override:
        return fw_override["start_command"]

    # Check package.json start script
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            start = data.get("scripts", {}).get("start")
            if start:
                return start
        except Exception:
            pass

    return LANGUAGE_DEFAULTS.get(language, {}).get("start_command", "")


def _detect_env_vars(root: Path) -> list[str]:
    """Collect env var keys from .env.example, .env, docker-compose.yml."""
    keys = set()

    for env_file in [root / ".env.example", root / ".env"]:
        if env_file.exists():
            content = env_file.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key = line.split("=", 1)[0].strip()
                    if key:
                        keys.add(key)

    # docker-compose environment section
    for compose_file in [root / "docker-compose.yml", root / "docker-compose.yaml"]:
        if compose_file.exists():
            content = compose_file.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"^\s+-\s+([A-Z_][A-Z0-9_]*)(?:=|$)", content, re.MULTILINE):
                keys.add(m.group(1))

    return sorted(keys)
