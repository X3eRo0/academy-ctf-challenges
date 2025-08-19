#!/bin/bash

# Password Manager Deployment Script  
# Starts both the crypto API and main web application

set -e

echo "=== Password Manager Deployment ==="

# Change to src directory
cd /app/src

echo "Starting crypto API service on port 3334..."
cd libvault
python crypto-api.py &
CRYPTO_PID=$!
echo "Crypto API started with PID: $CRYPTO_PID"

# Wait for crypto API to be ready
echo "Waiting for crypto API to start..."
sleep 5

# Test crypto API health
if curl -s http://localhost:3334/health > /dev/null; then
    echo "✓ Crypto API is healthy"
else
    echo "✗ Warning: Crypto API health check failed"
fi

echo "Starting password manager web application on port 3333..."
cd /app/src
python password-manager.py &
WEB_PID=$!
echo "Password manager started with PID: $WEB_PID"

# Setup signal handlers for graceful shutdown
cleanup() {
    echo "Shutting down services..."
    kill $CRYPTO_PID 2>/dev/null || true
    kill $WEB_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT

echo "=== Both services are running ==="
echo "- Crypto API: http://localhost:3334"
echo "- Password manager: http://localhost:3333"
echo "Press Ctrl+C to stop all services"

# Wait for either process to exit
wait $CRYPTO_PID $WEB_PID