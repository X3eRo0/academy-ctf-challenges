#!/bin/bash
set -e

# --- Configuration ---
export FLASK_APP=app.py
export BOT_PASSWORD=$(head /dev/urandom | tr -dc A-Za-z0-9 | head -c 16)
export ADMIN_PASSWORD=$(head /dev/urandom | tr -dc A-Za-z0-9 | head -c 16)

echo "--- Initializing Database ---"
flask initdb

echo "--- Populating with Bot Users and Posts ---"
# This script will now only create the users, not posts.
# python bots.py

echo "--- Setting Passwords ---"
# Set a secure, known password for all bot users and the admin
python -c "
import sqlite3
import os

BOT_PASSWORD = os.environ.get('BOT_PASSWORD')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

conn = sqlite3.connect('academygram.db')
# Set password for all users except admin
conn.execute('UPDATE users SET password = ? WHERE username != ?', (BOT_PASSWORD, 'admin'))
# Set admin password
conn.execute('UPDATE users SET password = ? WHERE username = ?', (ADMIN_PASSWORD, 'admin'))
conn.commit()
conn.close()
print('Bot and admin passwords have been set.')
"

echo "--- Starting Gunicorn ---"
exec gunicorn --bind 0.0.0.0:2750 --workers 4 app:app
