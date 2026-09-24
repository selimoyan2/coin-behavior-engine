# Coin Behavior Engine (CBE-0.7.0)
# Production Container for Coolify & Docker Deployment

FROM python:3.11-slim

# Prevent Python from buffering stdout/stderr and creating .pyc
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install project dependencies
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir "pandas>=2.2.0" "numpy>=1.26.0" "scipy>=1.12.0" "scikit-learn>=1.4.0" "pyarrow>=15.0.0" "requests>=2.31.0" "httpx>=0.27.0" "pydantic>=2.6.0" "pyyaml>=6.0.1" "matplotlib>=3.8.0"

# Copy source code and configuration
COPY src/ ./src/
COPY data/ ./data/
COPY config/ ./config/

# Install the engine package in editable/local mode
RUN pip install --no-cache-dir -e .

# Expose HTTP port for Coolify / Web monitoring
EXPOSE 8000

# Health check for Coolify / Docker
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the web monitoring server
CMD ["python", "-m", "coin_behavior_engine.web.server", "--host", "0.0.0.0", "--port", "8000"]
