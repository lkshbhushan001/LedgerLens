FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
# Ensure hatchling build tools find the README if declared
COPY README.md ./ 
# Copy source code BEFORE pip install
COPY app/ ./app/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir hatchling \
    && pip install --no-cache-dir . 
    # ^ Removed '-e' so the package is properly built into site-packages

# --- Production image ---
FROM python:3.11-slim-bookworm

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Because we used a standard 'pip install .', the code is now securely packaged 
# inside site-packages, making it safe to copy over to the prod image.
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]