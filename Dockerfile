# ── Stage 1: builder ──────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gosu && rm -rf /var/lib/apt/lists/*

RUN useradd -r -u 1000 -g root -s /sbin/nologin appuser

COPY --from=builder /install /usr/local

COPY . .

RUN mkdir -p static data && \
    chown -R appuser:root /app && \
    chmod -R 755 /app && \
    chmod 770 /app/data

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["/entrypoint.sh"]
