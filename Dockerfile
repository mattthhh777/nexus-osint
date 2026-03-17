# ── NexusOSINT Dockerfile ─────────────────────────────────────────────────────
# Python 3.10-slim base for a lean, production-ready image
FROM python:3.10-slim

# ── Labels ────────────────────────────────────────────────────────────────────
LABEL maintainer="NexusOSINT"
LABEL description="OSINT Investigation Dashboard"
LABEL version="1.0.0"

# ── Build args / env ──────────────────────────────────────────────────────────
# NOTE: Sensitive keys (OATHNET_API_KEY) are intentionally NOT set here.
# Pass them at runtime via --env-file or -e flags to avoid baking secrets into layers.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_THEME_BASE=dark \
    STREAMLIT_SERVER_HEADLESS=true

# ── System deps ───────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Python deps (layer-cached separately from source code) ───────────────────
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# ── Optional: install Sherlock CLI for subprocess fallback ────────────────────
RUN pip install sherlock-project || true

# ── Application source ────────────────────────────────────────────────────────
COPY . .

# ── Create writable directory for cases.json ─────────────────────────────────
RUN mkdir -p /data && chmod 777 /data
WORKDIR /data
ENV CASES_DIR=/data

# Re-set workdir so Streamlit can find app.py
WORKDIR /app

# ── Health-check ──────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# ── Expose ────────────────────────────────────────────────────────────────────
EXPOSE 8501

# ── Entrypoint ────────────────────────────────────────────────────────────────
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false", \
     "--theme.base=dark", \
     "--theme.backgroundColor=#0d1117", \
     "--theme.secondaryBackgroundColor=#161b22", \
     "--theme.textColor=#e6edf3", \
     "--theme.primaryColor=#00d4ff"]
