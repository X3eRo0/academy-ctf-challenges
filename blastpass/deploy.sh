#!/bin/bash

set -e

echo "=== BlastPass Deployment ==="

cd /app/src

echo "[+] Starting crypto API service on port 3334..."
cd libvault
python crypto-api.py &
CRYPTO_PID=$!

echo "[+] Crypto API started with PID: $CRYPTO_PID"
echo "[*] Waiting for crypto API to start..."
sleep 5

if curl -s http://localhost:3334/health >/dev/null; then
    echo "[+] Crypto API is healthy"
else
    echo "[-] Warning: Crypto API health check failed"
fi

echo "[+] Starting password manager web application on port 3333..."
cd /app/src
python blastpass.py &
WEB_PID=$!
echo "[+] Password manager started with PID: $WEB_PID"

cleanup() {
    echo "[-] Shutting down services..."
    kill $CRYPTO_PID 2>/dev/null || true
    kill $WEB_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT

echo "=== Both services are running ==="
echo "[+] Crypto API: http://localhost:3334"
echo "[+] Password manager: http://localhost:3333"
echo "Press Ctrl+C to stop all services"

wait $CRYPTO_PID $WEB_PID
