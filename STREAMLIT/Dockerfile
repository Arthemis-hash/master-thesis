# ============================================================
# STREAMLIT APPLICATION DOCKERFILE
# ============================================================
# Multi-stage build for optimized production image
# Stage 1: Build dependencies
# Stage 2: Production runtime
# ============================================================

# ============================================================
# STAGE 1: Builder - Install dependencies
# ============================================================
FROM python:3.11-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first (for better caching)
COPY airquality/app/requirements.txt .

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip wheel setuptools && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir psycopg2-binary bcrypt

# ============================================================
# STAGE 2: Production Runtime
# ============================================================
FROM python:3.11-slim-bookworm AS production

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    dumb-init \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# Create app directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY airquality/ /app/airquality/
COPY .env.example /app/
COPY STREAMLIT/.env /app/.env  # Mounted at runtime via docker-compose

# Create Streamlit config directory
RUN mkdir -p /app/.streamlit && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/-/healthz || exit 1

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Use dumb-init to handle signals properly
ENTRYPOINT ["dumb-init", "--"]

# Run Streamlit
CMD ["streamlit", "run", "airquality/app/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false", \
     "--theme.base=light"]
