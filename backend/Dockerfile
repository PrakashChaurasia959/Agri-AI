# ---------------------------------------------------------------------------
# AgriVision AI - API image
#
#   docker build -t agrivision-api ./backend
#   docker run --rm -p 8000:8000 --env-file backend/.env agrivision-api
# ---------------------------------------------------------------------------
FROM python:3.10-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# Pillow needs libjpeg/zlib; TensorFlow needs the standard BLAS stack.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libjpeg62-turbo-dev \
        zlib1g-dev \
        libpng-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# The model artifacts are mounted at runtime; create the directory so the
# container can start even when no model has been trained.
RUN mkdir -p /app/data/models /app/data/dataset /app/data/uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
