"""Default rules and configuration per language/framework."""

LANGUAGE_DEFAULTS = {
    "node": {
        "base_image": "node:20-alpine",
        "build_image": "node:20-alpine",
        "port": 3000,
        "start_command": "node index.js",
        "user": "node",
        "health_check_path": "/health",
        "package_manager": "npm",
    },
    "python": {
        "base_image": "python:3.12-slim",
        "port": 8000,
        "start_command": "python main.py",
        "user": "appuser",
        "health_check_path": "/health",
    },
    "java": {
        "build_image": "maven:3.9-eclipse-temurin-21",
        "base_image": "eclipse-temurin:21-jre-alpine",
        "port": 8080,
        "start_command": "java -jar app.jar",
        "user": "appuser",
        "health_check_path": "/actuator/health",
    },
    "go": {
        "build_image": "golang:1.22-alpine",
        "base_image": "scratch",
        "port": 8080,
        "start_command": "./app",
        "user": "",
        "health_check_path": "/health",
    },
    "dotnet": {
        "build_image": "mcr.microsoft.com/dotnet/sdk:8.0",
        "base_image": "mcr.microsoft.com/dotnet/aspnet:8.0",
        "port": 8080,
        "start_command": "dotnet app.dll",
        "user": "appuser",
        "health_check_path": "/health",
    },
}

FRAMEWORK_OVERRIDES = {
    "nextjs": {
        "base_image": "node:20-alpine",
        "port": 3000,
        "start_command": "node server.js",
        "has_build_step": True,
        "build_command": "npm run build",
    },
    "nestjs": {
        "port": 3000,
        "start_command": "node dist/main",
        "has_build_step": True,
        "build_command": "npm run build",
    },
    "fastapi": {
        "port": 8000,
        "start_command": "uvicorn main:app --host 0.0.0.0 --port 8000",
    },
    "django": {
        "port": 8000,
        "start_command": "gunicorn config.wsgi:application --bind 0.0.0.0:8000",
    },
    "flask": {
        "port": 5000,
        "start_command": "gunicorn app:app --bind 0.0.0.0:5000",
    },
    "springboot": {
        "port": 8080,
        "has_build_step": True,
        "build_command": "mvn package -DskipTests",
        "start_command": "java -jar target/*.jar",
    },
    "springboot_gradle": {
        "port": 8080,
        "has_build_step": True,
        "build_command": "./gradlew build -x test",
        "start_command": "java -jar build/libs/*.jar",
    },
}

K8S_DEFAULTS = {
    "replicas": 2,
    "service_type": "ClusterIP",
    "cpu_request": "250m",
    "memory_request": "256Mi",
    "cpu_limit": "500m",
    "memory_limit": "512Mi",
    "namespace": "default",
}
