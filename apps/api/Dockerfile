FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps: libmagic (MIME sniffing), poppler (PDF), tesseract (OCR).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml ./
COPY src ./src
RUN pip install -e ".[dev]"

COPY alembic.ini ./
COPY alembic ./alembic
COPY tests ./tests

EXPOSE 8000
CMD ["uvicorn", "sendpilot.main:app", "--host", "0.0.0.0", "--port", "8000"]
