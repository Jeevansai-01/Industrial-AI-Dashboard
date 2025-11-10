# syntax=docker/dockerfile:1

# --- Base Stage ---
FROM python:3.11-slim as base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends tini && \
    rm -rf /var/lib/apt/lists/*

# --- Builder Stage ---
FROM base as builder
# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*
    
# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Final Stage ---
FROM base
# Create a non-root user
RUN addgroup --system app && adduser --system --group app

# Copy installed dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy application code
COPY . .



# --- FIX: Move chown to be the last command before USER ---
# This ensures all copied files are owned by the correct user.
RUN chown -R app:app /app

# Now, switch to the non-root user
USER app

# Set environment variables
ENV FLASK_APP=app.py \
    FLASK_ENV=production \
    DB_PATH=/app/data/sensor_data.db \
    GUNICORN_WORKERS=2 \
    GUNICORN_THREADS=4

EXPOSE 5000
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "gunicorn", "--bind=0.0.0.0:5000", "app:app"]
