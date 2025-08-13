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
    socat \
    && rm -rf /var/lib/apt/lists/*

# Set up Python environment
RUN python3 -m pip install --upgrade pip

# Create necessary directories
RUN mkdir -p /root/xvm

# Set working directory
WORKDIR /root/xvm

COPY ./build/xvm /root/xvm/
COPY ./build/xinfo /root/xvm/
COPY ./build/xasm /root/xvm/
COPY ./build/xdbg /root/xvm/
COPY ./build/xdis /root/xvm/
COPY server.py /root/xvm

RUN groupadd -g 1000 ctf && useradd -r -u 1000 -g 1000 -s /bin/false ctf

# Expose the service port
EXPOSE 7777

# Health check
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#     CMD curl -f http://localhost:5000/ || exit 1

WORKDIR /root/xvm
CMD ["socat", "TCP-LISTEN:7777,reuseaddr,fork", "EXEC:'python3 server.py'"]
