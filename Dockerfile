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

# Copy frontend directories if they exist (using COPY with error handling)
COPY templates/ /workspace/templates/ 2>/dev/null || true
COPY static/ /workspace/static/ 2>/dev/null || true
COPY frontend/ /workspace/frontend/ 2>/dev/null || true

# Create data directory and set permissions
RUN mkdir -p /workspace/data/projects && chmod -R 777 /workspace/data

# Expose only port 5000
EXPOSE 5000

# Run the application directly
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "5000"]
