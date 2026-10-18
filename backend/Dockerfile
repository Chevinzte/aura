FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN python -m pip install --no-cache-dir .

RUN useradd --create-home aura
USER aura

CMD ["sh", "-c", "exec python -m uvicorn aura_backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
