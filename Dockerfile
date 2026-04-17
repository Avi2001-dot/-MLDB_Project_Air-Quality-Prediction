FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    openjdk-11-jre-headless \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p data/bronze data/silver data/gold data/models logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SPARK_LOCAL_IP=127.0.0.1
ENV PYSPARK_PYTHON=/usr/local/bin/python

# Expose ports
EXPOSE 8501 9092

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Default command
CMD ["python", "run_pipeline.py"]
