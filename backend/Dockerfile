# Use python-slim for a smaller footprint
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN adduser --disabled-password --gecos "" mediflowuser

WORKDIR /app

# Install Python dependencies (CPU only to save RAM and avoid GPU issues)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set permissions
RUN chown -R mediflowuser:mediflowuser /app /tmp/mediflow
USER mediflowuser

EXPOSE 8000

# Run with uvicorn, optimizing for limited RAM
# Single worker: model singleton loads once (~1.5 GB RAM).
# 2 workers = 2 model copies = ~3 GB = OOM on 4 GB VM.
CMD ["uvicorn", "main:app", \
    "--host", "0.0.0.0", \
    "--port", "8000", \
    "--workers", "1", \
    "--timeout-keep-alive", "35"]
