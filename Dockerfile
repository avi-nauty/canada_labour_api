FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --locked --no-dev --no-install-project

COPY app ./app

ENV PATH="/app/.venv/bin:$PATH"

CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}