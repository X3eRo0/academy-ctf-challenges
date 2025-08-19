FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    make \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY src/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY exploits/ ./exploits/
COPY deploy.sh ./

# Create directories for vault storage
RUN mkdir -p /app/vaults

# Set working directory to src
WORKDIR /app/src

# Build C crypto library
RUN cd libvault && make

# Expose ports for both services
EXPOSE 3333 3334

# Set environment variables
ENV FLASK_APP=password-manager.py
ENV FLASK_ENV=production

# Make deploy script executable
RUN chmod +x /app/deploy.sh

# Run both applications using deploy script
CMD ["/app/deploy.sh"]