FROM ghcr.io/astral-sh/uv:python3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev --no-editable

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src/ ./src/
COPY main.py ./

ENV PATH="/app/.venv/bin:$PATH"

RUN mkdir -p /data/actual-sync /config

EXPOSE 3000
CMD ["python", "main.py"]
