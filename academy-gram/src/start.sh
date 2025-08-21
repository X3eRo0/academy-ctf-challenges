#!/bin/bash
set -e

# --- Configuration ---
export FLASK_APP=app.py

echo "--- Initializing Database ---"
flask initdb
echo "--- Starting Gunicorn ---"
exec gunicorn --bind 0.0.0.0:2750 --workers 4 app:app
