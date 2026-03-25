# ============================================================================
# CoHabitant — Production Dockerfile for Azure Web Apps
# ============================================================================
# Installs Python, Streamlit, Microsoft ODBC Driver 17 for SQL Server,
# and all application dependencies in a single optimized image.
#
# Build:  docker build -t cohabitant:latest ./streamlit_app
# Run:    docker run -p 8501:8501 --env-file .env cohabitant:latest
#
# Azure deployment:
#   az webapp create --resource-group <rg> --plan <plan> \
#     --name cohabitant --deployment-container-image-name <acr>.azurecr.io/cohabitant:latest
# ============================================================================

FROM python:3.11-slim-bookworm AS base

# ── Metadata ──
LABEL maintainer="CoHabitant Team"
LABEL description="CoHabitant SaaS — Streamlit + SQL Server multi-tenant app"

# ── System dependencies + Microsoft ODBC 17 driver ──
# This is the critical piece for Azure SQL / SQL Server connectivity.
# The driver must match the version in your connection string ({ODBC Driver 17 for SQL Server}).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg2 \
    apt-transport-https \
    unixodbc \
    unixodbc-dev \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
       > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 \
    && apt-get purge -y --auto-remove curl gnupg2 apt-transport-https \
    && rm -rf /var/lib/apt/lists/*

# ── Python environment ──
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ── Install Python dependencies (cached layer — only rebuilds when requirements.txt changes) ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy application code ──
COPY . .

# ── Streamlit configuration ──
# Ensure headless mode for container environments
RUN mkdir -p /app/.streamlit
COPY .streamlit/config.toml /app/.streamlit/config.toml

# ── Health check for Azure App Service ──
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# ── Expose Streamlit default port ──
EXPOSE 8501

# ── Entrypoint ──
# Azure Web Apps expects the container to listen on $PORT (defaults to 8501).
# --server.address=0.0.0.0 is required for container networking.
ENTRYPOINT ["streamlit", "run", "app.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--browser.gatherUsageStats=false"]
