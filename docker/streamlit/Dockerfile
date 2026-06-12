FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates libgomp1 openssl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    APP_CONFIG=config.toml \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

# Pydantic settings expect JWT key files; Streamlit does not serve auth endpoints.
RUN mkdir -p app/certs \
    && openssl genrsa -out app/certs/jwt-private.pem 2048 \
    && openssl rsa -in app/certs/jwt-private.pem -outform PEM -pubout -out app/certs/jwt-public.pem

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --retries=5 --start-period=120s \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["uv", "run", "streamlit", "run", "streamlit_app.py"]
