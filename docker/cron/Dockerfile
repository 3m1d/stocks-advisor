FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates libgomp1 openssl cron \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    APP_CONFIG=config.toml \
    TZ=Europe/Moscow

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

# Pydantic settings expect JWT key files; cron jobs do not serve auth endpoints.
RUN mkdir -p app/certs \
    && openssl genrsa -out app/certs/jwt-private.pem 2048 \
    && openssl rsa -in app/certs/jwt-private.pem -outform PEM -pubout -out app/certs/jwt-public.pem

RUN mkdir -p /var/log/cron \
    && chmod +x docker/cron/run-job.sh docker/cron/entrypoint.sh \
    && cp docker/cron/crontab /etc/cron.d/stocks-advisor \
    && chmod 0644 /etc/cron.d/stocks-advisor

ENTRYPOINT ["/app/docker/cron/entrypoint.sh"]
