FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-noto-cjk \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "google-genai>=1.0.0" \
    "pyyaml>=6.0" \
    "requests>=2.30.0" \
    "pillow>=10.0.0" \
    "zhconv>=1.4.3" \
    "streamlit>=1.35.0" \
    "fastapi>=0.110.0" \
    "uvicorn[standard]>=0.28.0"

WORKDIR /workspace
