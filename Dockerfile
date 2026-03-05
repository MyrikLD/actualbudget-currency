FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev --no-editable

COPY src/ ./src/
COPY main.py ./

ENV PATH="/app/.venv/bin:$PATH"

RUN mkdir -p /data/actual-sync /config

EXPOSE 3000
CMD ["python", "main.py"]
