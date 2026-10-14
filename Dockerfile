FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first: this layer is rebuilt only when the lock file changes.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY deribit_tracker ./deribit_tracker
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 1000 tracker
USER tracker

EXPOSE 8000
CMD ["uvicorn", "deribit_tracker.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
