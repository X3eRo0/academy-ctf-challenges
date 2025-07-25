# Use Ubuntu as base image for better compatibility with CTF gameserver
FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    wget \
    sqlite3 \
    sudo \
    cowsay \
    && rm -rf /var/lib/apt/lists/*

# Set up Python environment
RUN python3 -m pip install --upgrade pip

# Create necessary directories
RUN mkdir -p /root/cowsay

# Set working directory
WORKDIR /root/cowsay

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies globally (for both root and ctf-checkerrunner)
RUN pip3 install -r requirements.txt

# Copy service files
COPY server.py .

# Expose the service port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

CMD ["python3", "/root/cowsay/server.py"]

