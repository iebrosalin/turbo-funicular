FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies including git
RUN apt-get update && apt-get install -y \
    git \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install Python dependencies
COPY app/backend/requirements.txt /workspace/backend/requirements.txt
RUN pip install --no-cache-dir -r /workspace/backend/requirements.txt

# Copy application code
COPY backend/ /workspace/backend/

# Copy frontend directories
COPY templates/ /workspace/templates/
COPY static/ /workspace/static/
COPY frontend/ /workspace/frontend/

# Create data directory and set permissions (will be overridden by volume mount)
# The actual directory creation happens at runtime via entrypoint or init script
RUN mkdir -p /workspace/data/projects && chmod -R 777 /workspace/data

# Expose only port 5000
EXPOSE 5000

# Create data directory at runtime if it doesn't exist and start the application
CMD ["sh", "-c", "mkdir -p /workspace/data && chmod -R 777 /workspace/data && uvicorn backend.main:app --host 0.0.0.0 --port 5000"]
