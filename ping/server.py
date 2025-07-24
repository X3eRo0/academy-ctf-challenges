#!/usr/bin/env python3

import sqlite3
import hashlib
import subprocess
import shlex
import re
import os
from flask import (
    Flask,
    request,
    render_template_string,
    redirect,
    url_for,
    session,
    flash,
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)


# Database setup
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  message TEXT NOT NULL)"""
    )
    conn.commit()
    conn.close()


def get_db_connection():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    return conn


# HTML templates
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Ping Service - Login</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 50px; }
        .container { max-width: 400px; margin: 0 auto; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; }
        input[type="text"], input[type="password"], textarea { width: 100%; padding: 8px; box-sizing: border-box; }
        button { background-color: #007cba; color: white; padding: 10px 20px; border: none; cursor: pointer; }
        button:hover { background-color: #005a87; }
        .error { color: red; }
        .links { text-align: center; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Login to Ping Service</h2>
        {% if error %}
            <div class="error">{{ error }}</div>
        {% endif %}
        <form method="post">
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit">Login</button>
        </form>
        <div class="links">
            <a href="{{ url_for('register') }}">Don't have an account? Register here</a>
        </div>
    </div>
</body>
</html>
"""

REGISTER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Ping Service - Register</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 50px; }
        .container { max-width: 400px; margin: 0 auto; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; }
        input[type="text"], input[type="password"], textarea { width: 100%; padding: 8px; box-sizing: border-box; }
        textarea { height: 100px; resize: vertical; }
        button { background-color: #007cba; color: white; padding: 10px 20px; border: none; cursor: pointer; }
        button:hover { background-color: #005a87; }
        .error { color: red; }
        .links { text-align: center; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Register for Ping Service</h2>
        {% if error %}
            <div class="error">{{ error }}</div>
        {% endif %}
        <form method="post">
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <div class="form-group">
                <label for="message">Message:</label>
                <textarea id="message" name="message" placeholder="Enter your message here..." required></textarea>
            </div>
            <button type="submit">Register</button>
        </form>
        <div class="links">
            <a href="{{ url_for('login') }}">Already have an account? Login here</a>
        </div>
    </div>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Ping Service - Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 50px; }
        .container { max-width: 800px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; }
        input[type="text"] { width: 300px; padding: 8px; }
        button { background-color: #007cba; color: white; padding: 10px 20px; border: none; cursor: pointer; margin-right: 10px; }
        button:hover { background-color: #005a87; }
        .logout { background-color: #dc3545; }
        .logout:hover { background-color: #c82333; }
        .output { background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; margin-top: 20px; white-space: pre-line; font-family: monospace; }
        .error { color: red; }
        .message-box { background-color: #e7f3ff; border: 1px solid #b8d4f0; padding: 15px; margin-bottom: 20px; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Welcome, {{ username }}!</h2>
            <form method="post" action="{{ url_for('logout') }}" style="margin: 0;">
                <button type="submit" class="logout">Logout</button>
            </form>
        </div>
        
        <div class="message-box">
            <h3>Your Message:</h3>
            <p>{{ user_message }}</p>
        </div>
        
        <h3>Ping Tool</h3>
        {% if error %}
            <div class="error">{{ error }}</div>
        {% endif %}
        <form method="post">
            <div class="form-group">
                <label for="ip">IP Address or Hostname:</label>
                <input type="text" id="ip" name="ip" placeholder="e.g., 8.8.8.8 or google.com" required>
            </div>
            <button type="submit">Ping</button>
        </form>
        
        {% if ping_output %}
        <div class="output">{{ ping_output }}</div>
        {% endif %}
    </div>
</body>
</html>
"""


def is_valid_ip_or_hostname(target):
    """Validate IP address or hostname to prevent command injection"""
    # Allow only alphanumeric characters, dots, hyphens, and underscores
    # This prevents command injection while allowing valid IPs and hostnames
    if not re.match(r"^[a-zA-Z0-9._-]+$", target):
        return False

    # Additional length check
    if len(target) > 255:
        return False

    # Prevent consecutive dots which could be path traversal attempts
    if ".." in target:
        return False

    return True


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        message = request.form["message"].strip()

        if not username or not password or not message:
            return render_template_string(
                REGISTER_TEMPLATE, error="All fields are required"
            )

        # Basic validation
        if len(username) < 3 or len(username) > 50:
            return render_template_string(
                REGISTER_TEMPLATE, error="Username must be between 3 and 50 characters"
            )

        if len(password) < 6:
            return render_template_string(
                REGISTER_TEMPLATE, error="Password must be at least 6 characters"
            )

        if len(message) > 1000:
            return render_template_string(
                REGISTER_TEMPLATE, error="Message too long (max 1000 characters)"
            )

        try:
            conn = get_db_connection()
            password_hash = generate_password_hash(password)
            conn.execute(
                "INSERT INTO users (username, password_hash, message) VALUES (?, ?, ?)",
                (username, password_hash, message),
            )
            conn.commit()
            conn.close()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return render_template_string(
                REGISTER_TEMPLATE, error="Username already exists"
            )

    return render_template_string(REGISTER_TEMPLATE)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or not password:
            return render_template_string(
                LOGIN_TEMPLATE, error="Username and password are required"
            )

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        else:
            return render_template_string(
                LOGIN_TEMPLATE, error="Invalid username or password"
            )

    return render_template_string(LOGIN_TEMPLATE)


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Get user's message
    conn = get_db_connection()
    user = conn.execute(
        "SELECT message FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()
    conn.close()

    user_message = user["message"] if user else "No message found"
    ping_output = None
    error = None

    if request.method == "POST":
        ip = request.form["ip"].strip()

        if not ip:
            error = "Please enter an IP address or hostname"
        elif not is_valid_ip_or_hostname(ip):
            error = "Invalid IP address or hostname format"
        else:
            try:
                # Use shlex.quote for additional safety, even though we've validated the input
                safe_ip = shlex.quote(ip)
                # Execute ping command safely
                result = subprocess.run(
                    ["ping", "-c", "1", ip],  # Using list form prevents shell injection
                    capture_output=True,
                    text=True,
                    timeout=30,  # Prevent hanging
                )

                if result.returncode == 0:
                    ping_output = result.stdout
                else:
                    ping_output = f"Ping failed:\nret: {result.returncode}"

            except subprocess.TimeoutExpired:
                error = "Ping operation timed out"
            except Exception as e:
                error = f"Error executing ping: {str(e)}"

    return render_template_string(
        DASHBOARD_TEMPLATE,
        username=session["username"],
        user_message=user_message,
        ping_output=ping_output,
        error=error,
    )


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
