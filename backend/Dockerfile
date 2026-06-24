FROM python:3.12-slim

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential wget \
    && rm -rf /var/lib/apt/lists/*

# Download and install cloudflared
RUN wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared \
    && chmod +x /usr/local/bin/cloudflared

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files
COPY . ./backend

# Make entrypoint script executable
RUN chmod +x ./backend/entrypoint.sh

# Expose FastAPI port
EXPOSE 8000

# Set Python path to ensure imports work correctly
ENV PYTHONPATH=/app

# Start application via entrypoint script
CMD ["/bin/sh", "./backend/entrypoint.sh"]
