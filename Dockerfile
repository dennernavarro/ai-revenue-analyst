# Stage 1: install dependencies with uv (bytecode-compiled, locked versions)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Stage 2: slim runtime image without uv or build tooling
FROM python:3.12-slim-bookworm
WORKDIR /app

RUN useradd --create-home analyst
COPY --from=builder --chown=analyst:analyst /app /app
RUN mkdir -p /app/.state && chown analyst:analyst /app /app/.state
USER analyst

ENV PATH="/app/.venv/bin:$PATH" \
    RA_STATE_DIR=/app/.state

EXPOSE 8000
CMD ["uvicorn", "revenue_analyst.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
