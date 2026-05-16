FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies including git
RUN apt-get update && apt-get install -y \
    git \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install Python dependencies
COPY app/backend/requirements.txt /workspace/backend/
RUN pip install --no-cache-dir -r /workspace/backend/requirements.txt

# Copy application code
COPY app/backend/ /workspace/backend/
COPY templates/ /workspace/templates/
COPY static/ /workspace/static/
COPY frontend/ /workspace/frontend/

# Create data directory
RUN mkdir -p /workspace/data/projects

# Expose only port 5000
EXPOSE 5000

# Start only the FastAPI backend
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "5000"]
