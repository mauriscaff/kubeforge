"""KubeForge — FastAPI application entry point."""

import asyncio
import io
import os
import shutil
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from analyzer import detector, parser
from analyzer.rules import FRAMEWORK_OVERRIDES, K8S_DEFAULTS, LANGUAGE_DEFAULTS
from generator import dockerfile_gen, k8s_gen

app = FastAPI(title="KubeForge", version="1.0.0")

# Serve frontend
app.mount("/static", StaticFiles(directory="views"), name="static")

# In-memory session store: session_id -> temp_dir path
_sessions: dict[str, dict] = {}

SESSIONS_TTL = 1800  # 30 minutes


def _cleanup_old_sessions():
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s["created_at"] > SESSIONS_TTL]
    for sid in expired:
        tmp = _sessions.pop(sid, {}).get("tmp_dir")
        if tmp and Path(tmp).exists():
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def index():
    return FileResponse("views/index.html")


@app.post("/analyze")
async def analyze(
    source_type: str = Form(...),
    folder_path: Optional[str] = Form(None),
    git_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """
    Receives source code (folder path, zip upload, or git URL),
    analyzes it, and returns detected configuration.
    """
    _cleanup_old_sessions()

    session_id = str(uuid.uuid4())
    tmp_dir = tempfile.mkdtemp(prefix=f"kubeforge-{session_id}-")

    try:
        project_path = await _prepare_source(source_type, folder_path, git_url, file, tmp_dir)
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e))

    detected = detector.detect(project_path)
    language = detected["language"]
    framework = detected["framework"]

    if language == "unknown":
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=422,
            detail="Não foi possível detectar a linguagem. Por favor, selecione manualmente.",
        )

    parsed = parser.parse(project_path, language, framework)

    _sessions[session_id] = {"tmp_dir": tmp_dir, "created_at": time.time()}

    lang_defaults = LANGUAGE_DEFAULTS.get(language, {})
    fw_overrides = FRAMEWORK_OVERRIDES.get(framework, {})

    return {
        "session_id": session_id,
        "language": language,
        "framework": framework,
        "build_tool": detected.get("build_tool", ""),
        "has_build_step": detected.get("has_build_step", False),
        "port": parsed["port"],
        "start_command": parsed["start_command"],
        "env_vars": [{"key": k, "value": ""} for k in parsed["env_vars"]],
        "base_image": fw_overrides.get("base_image") or lang_defaults.get("base_image", ""),
        "build_image": lang_defaults.get("build_image", ""),
        "user": lang_defaults.get("user", "appuser"),
        "health_check_path": lang_defaults.get("health_check_path", "/health"),
        "k8s_defaults": K8S_DEFAULTS,
    }


class GenerateRequest(BaseModel):
    session_id: str
    # App config
    app_name: str
    namespace: str = "default"
    language: str
    framework: str
    build_tool: str = ""
    # Dockerfile
    port: int
    has_build_step: bool = False
    start_command: str
    build_command: str = ""
    base_image: str
    build_image: str = ""
    package_manager: str = "npm"
    user: str = "appuser"
    env_vars: list[dict] = []
    # K8s
    replicas: int = 2
    service_type: str = "ClusterIP"
    image_name: str = ""
    image_tag: str = "latest"
    cpu_request: str = "250m"
    memory_request: str = "256Mi"
    cpu_limit: str = "500m"
    memory_limit: str = "512Mi"
    health_check_path: str = "/health"


@app.post("/generate")
async def generate(req: GenerateRequest):
    """Generates all files and returns their content as JSON."""

    if not req.image_name:
        req.image_name = f"registry.example.com/{req.app_name}"

    # --- Dockerfile ---
    df_ctx = {
        "language": req.language,
        "framework": req.framework,
        "build_tool": req.build_tool,
        "base_image": req.base_image,
        "build_image": req.build_image,
        "port": req.port,
        "user": req.user,
        "start_command": req.start_command,
        "build_command": req.build_command,
        "has_build_step": req.has_build_step,
        "package_manager": req.package_manager,
    }
    try:
        dockerfile_content = dockerfile_gen.generate(df_ctx)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao gerar o Dockerfile: {e}")

    # --- K8s manifests ---
    k8s_ctx = {
        "app_name": req.app_name,
        "namespace": req.namespace,
        "language": req.language,
        "replicas": req.replicas,
        "service_type": req.service_type,
        "image_name": req.image_name,
        "image_tag": req.image_tag,
        "port": req.port,
        "cpu_request": req.cpu_request,
        "memory_request": req.memory_request,
        "cpu_limit": req.cpu_limit,
        "memory_limit": req.memory_limit,
        "env_vars": req.env_vars,
        "health_check_path": req.health_check_path,
    }
    try:
        k8s_files = k8s_gen.generate(k8s_ctx)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao gerar os manifests K8s: {e}")

    # --- Scripts ---
    scripts = _generate_scripts(req.app_name, req.image_name, req.namespace)

    files = {"Dockerfile": dockerfile_content, **k8s_files, **scripts}

    return {"files": files}


class DownloadRequest(BaseModel):
    app_name: str
    files: dict[str, str]


@app.post("/download")
async def download(req: DownloadRequest):
    """Packages all files into a .zip and streams it back."""
    buf = io.BytesIO()
    base = f"{req.app_name}-k8s"

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in req.files.items():
            zf.writestr(f"{base}/{filename}", content)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{base}.zip"'},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _prepare_source(
    source_type: str,
    folder_path: Optional[str],
    git_url: Optional[str],
    file: Optional[UploadFile],
    tmp_dir: str,
) -> str:
    """Returns the path to the project directory inside tmp_dir."""
    project_dir = os.path.join(tmp_dir, "project")

    if source_type == "folder":
        if not folder_path:
            raise ValueError("O campo folder_path é obrigatório para source_type=folder.")
        if not Path(folder_path).is_dir():
            raise ValueError(f"Diretório não encontrado: {folder_path}")
        # Use directly — no copy needed for analysis
        return folder_path

    elif source_type == "zip":
        if not file:
            raise ValueError("O upload do arquivo é obrigatório para source_type=zip.")
        zip_path = os.path.join(tmp_dir, "upload.zip")
        content = await file.read()
        with open(zip_path, "wb") as f:
            f.write(content)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(project_dir)
        except zipfile.BadZipFile:
            raise ValueError("Arquivo .zip inválido ou corrompido.")
        # If zip has a single root directory, descend into it
        entries = list(Path(project_dir).iterdir())
        if len(entries) == 1 and entries[0].is_dir():
            return str(entries[0])
        return project_dir

    elif source_type == "git":
        if not git_url:
            raise ValueError("O campo git_url é obrigatório para source_type=git.")
        try:
            import git as gitpython
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: gitpython.Repo.clone_from(git_url, project_dir, depth=1, no_single_branch=True),
            )
        except Exception as e:
            raise ValueError(f"Falha ao clonar o repositório: {e}")
        return project_dir

    else:
        raise ValueError(f"Tipo de fonte desconhecido: {source_type}")


def _generate_scripts(app_name: str, image_name: str, namespace: str) -> dict[str, str]:
    deploy = f"""#!/usr/bin/env bash
# deploy.sh — Aplica os manifests K8s com kustomize
set -euo pipefail

NAMESPACE="{namespace}"

echo "🚀 Implantando {app_name} no namespace: $NAMESPACE"
kubectl apply -k .
kubectl rollout status deployment/{app_name} -n "$NAMESPACE" --timeout=120s
echo "✅ Implantação concluída"
"""

    rollback = f"""#!/usr/bin/env bash
# rollback.sh — Reverte para a revisão anterior do deployment
set -euo pipefail

NAMESPACE="{namespace}"
DEPLOYMENT="{app_name}"

echo "⏪ Revertendo $DEPLOYMENT no namespace: $NAMESPACE"
kubectl rollout undo deployment/"$DEPLOYMENT" -n "$NAMESPACE"
kubectl rollout status deployment/"$DEPLOYMENT" -n "$NAMESPACE" --timeout=120s
echo "✅ Reversão concluída"
"""

    build_push = f"""#!/usr/bin/env bash
# build-push.sh — Faz o build da imagem Docker e envia para o registry
set -euo pipefail

IMAGE="{image_name}"
TAG="${{1:-latest}}"

echo "🐳 Fazendo build da imagem: $IMAGE:$TAG"
docker build -t "$IMAGE:$TAG" .

echo "📤 Enviando imagem: $IMAGE:$TAG"
docker push "$IMAGE:$TAG"

echo "✅ Concluído: $IMAGE:$TAG"
"""

    return {
        "scripts/deploy.sh": deploy,
        "scripts/rollback.sh": rollback,
        "scripts/build-push.sh": build_push,
    }
