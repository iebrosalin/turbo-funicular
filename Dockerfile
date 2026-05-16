FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including git
RUN apt-get update && apt-get install -y \
    git \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install Python dependencies
COPY app/backend/requirements.txt /app/backend/
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy frontend files and install dependencies
COPY app/frontend/package*.json /app/frontend/
WORKDIR /app/frontend
RUN npm install

# Copy application code
WORKDIR /app
COPY app/ /app/

# Create data directory
RUN mkdir -p /app/data/projects

# Expose ports
EXPOSE 5000 3000

# Start both services
CMD ["sh", "-c", "cd /app/backend && python app.py & cd /app/frontend && npm run dev"]
