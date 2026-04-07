"""Detects language and framework from project file structure."""

import json
import os
from pathlib import Path


def detect(project_path: str) -> dict:
    """
    Walk the project directory and return detected language/framework info.
    Returns dict with: language, framework, has_build_step, build_tool
    """
    root = Path(project_path)
    files = _list_files(root)

    language, framework, build_tool = _detect_language_framework(root, files)

    return {
        "language": language,
        "framework": framework,
        "build_tool": build_tool,
        "has_build_step": _has_build_step(framework),
    }


def _list_files(root: Path, max_depth: int = 3) -> set[str]:
    """Return set of relative file paths up to max_depth."""
    result = set()
    for dirpath, dirnames, filenames in os.walk(root):
        depth = len(Path(dirpath).relative_to(root).parts)
        if depth > max_depth:
            dirnames.clear()
            continue
        # Skip hidden and common non-source dirs
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d not in {"node_modules", "__pycache__", ".git", "dist", "build", "target"}
        ]
        for f in filenames:
            rel = str(Path(dirpath).relative_to(root) / f)
            result.add(rel.replace("\\", "/"))
    return result


def _detect_language_framework(root: Path, files: set[str]) -> tuple[str, str, str]:
    """Return (language, framework, build_tool)."""

    # --- Node.js ---
    if "package.json" in files or any(f.endswith("/package.json") for f in files):
        pkg_path = root / "package.json"
        if pkg_path.exists():
            try:
                pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
            except Exception:
                pkg = {}

            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            if "next" in deps or any(f in files for f in ["next.config.js", "next.config.ts", "next.config.mjs"]):
                return "node", "nextjs", "npm"
            if "@nestjs/core" in deps or "nest-cli.json" in files:
                return "node", "nestjs", "npm"
            if "express" in deps:
                return "node", "express", "npm"
            if "fastify" in deps:
                return "node", "fastify", "npm"

            pkg_manager = "yarn" if "yarn.lock" in files else ("pnpm" if "pnpm-lock.yaml" in files else "npm")
            return "node", "node", pkg_manager

    # --- Python ---
    has_requirements = "requirements.txt" in files
    has_pyproject = "pyproject.toml" in files

    if has_requirements or has_pyproject or any(f.endswith(".py") for f in files):
        req_content = ""
        if has_requirements:
            try:
                req_content = (root / "requirements.txt").read_text(encoding="utf-8").lower()
            except Exception:
                pass

        pyproject_content = ""
        if has_pyproject:
            try:
                pyproject_content = (root / "pyproject.toml").read_text(encoding="utf-8").lower()
            except Exception:
                pass

        combined = req_content + pyproject_content

        if "fastapi" in combined:
            return "python", "fastapi", "pip"
        if "django" in combined:
            return "python", "django", "pip"
        if "flask" in combined:
            return "python", "flask", "pip"

        return "python", "python", "pip"

    # --- Java ---
    if "pom.xml" in files:
        try:
            pom = (root / "pom.xml").read_text(encoding="utf-8").lower()
            if "spring-boot" in pom:
                return "java", "springboot", "maven"
        except Exception:
            pass
        return "java", "java", "maven"

    if "build.gradle" in files or "build.gradle.kts" in files:
        try:
            gradle_file = "build.gradle" if "build.gradle" in files else "build.gradle.kts"
            gradle = (root / gradle_file).read_text(encoding="utf-8").lower()
            if "spring" in gradle:
                return "java", "springboot_gradle", "gradle"
        except Exception:
            pass
        return "java", "java", "gradle"

    # --- Go ---
    if "go.mod" in files:
        return "go", "go", "go"

    # --- .NET ---
    csproj = next((f for f in files if f.endswith(".csproj")), None)
    sln = next((f for f in files if f.endswith(".sln")), None)
    if csproj or sln:
        return "dotnet", "aspnet", "dotnet"

    return "unknown", "unknown", "unknown"


def _has_build_step(framework: str) -> bool:
    BUILD_STEP_FRAMEWORKS = {"nextjs", "nestjs", "springboot", "springboot_gradle"}
    return framework in BUILD_STEP_FRAMEWORKS
