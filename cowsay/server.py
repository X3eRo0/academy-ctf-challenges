#!/usr/bin/env python3

import sqlite3
import hashlib
import os
import subprocess
import shlex  # Keep import but don't use for the vulnerability
from flask import (
    Flask,
    render_template_string,
    request,
    redirect,
    url_for,
    session,
    flash,
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Database setup
DATABASE = "users.db"


def init_db():
    """Initialize the database with users table"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            message TEXT NOT NULL
        )
    """
    )
    conn.commit()
    conn.close()


def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# HTML Templates
REGISTER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>CTF Service - Register</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 500px; margin: 50px auto; padding: 20px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; }
        input[type="text"], input[type="password"], textarea { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
        input[type="submit"] { background-color: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        input[type="submit"]:hover { background-color: #0056b3; }
        .error { color: red; margin-bottom: 15px; }
        .nav { margin-bottom: 20px; }
        .nav a { margin-right: 10px; text-decoration: none; color: #007bff; }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/">Home</a>
        <a href="/login">Login</a>
        <a href="/register">Register</a>
    </div>
    <h1>Register</h1>
    {% if error %}
        <div class="error">{{ error }}</div>
    {% endif %}
    <form method="POST">
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
            <textarea id="message" name="message" rows="4" required></textarea>
        </div>
        <input type="submit" value="Register">
    </form>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>CTF Service - Login</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 500px; margin: 50px auto; padding: 20px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; }
        input[type="text"], input[type="password"] { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
        input[type="submit"] { background-color: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        input[type="submit"]:hover { background-color: #0056b3; }
        .error { color: red; margin-bottom: 15px; }
        .nav { margin-bottom: 20px; }
        .nav a { margin-right: 10px; text-decoration: none; color: #007bff; }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/">Home</a>
        <a href="/login">Login</a>
        <a href="/register">Register</a>
    </div>
    <h1>Login</h1>
    {% if error %}
        <div class="error">{{ error }}</div>
    {% endif %}
    <form method="POST">
        <div class="form-group">
            <label for="username">Username:</label>
            <input type="text" id="username" name="username" required>
        </div>
        <div class="form-group">
            <label for="password">Password:</label>
            <input type="password" id="password" name="password" required>
        </div>
        <input type="submit" value="Login">
    </form>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>CTF Service - Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; }
        input[type="text"] { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
        input[type="submit"] { background-color: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        input[type="submit"]:hover { background-color: #218838; }
        .nav { margin-bottom: 20px; }
        .nav a { margin-right: 10px; text-decoration: none; color: #007bff; }
        .logout { color: #dc3545; }
        .output { background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin-top: 20px; white-space: pre-wrap; font-family: monospace; }
        .user-info { background-color: #e9ecef; padding: 10px; border-radius: 4px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/">Home</a>
        <a href="/logout" class="logout">Logout</a>
    </div>
    <h1>Welcome, {{ username }}!</h1>
    <div class="user-info">
        <strong>Your message:</strong> {{ user_message }}
    </div>
    <h2>Cowsay Generator</h2>
    <form method="POST">
        <div class="form-group">
            <label for="input_text">Enter text for cowsay:</label>
            <input type="text" id="input_text" name="input_text" placeholder="Hello, world!" required>
        </div>
        <input type="submit" value="Generate Cowsay">
    </form>
    {% if output %}
        <div class="output">{{ output }}</div>
    {% endif %}
</body>
</html>
"""

HOME_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>CTF Service</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; }
        .nav { margin-bottom: 30px; }
        .nav a { margin: 0 15px; text-decoration: none; color: #007bff; font-size: 18px; }
        .nav a:hover { text-decoration: underline; }
        h1 { color: #333; }
        .description { margin: 30px 0; color: #666; line-height: 1.6; }
    </style>
</head>
<body>
    <h1>Welcome to CTF Service</h1>
    <div class="description">
        <p>This is a simple service that allows you to register, login, and generate ASCII art using cowsay!</p>
        <p>Register to get started or login if you already have an account.</p>
    </div>
    <div class="nav">
        <a href="/register">Register</a>
        <a href="/login">Login</a>
    </div>
</body>
</html>
"""


@app.route("/")
def home():
    """Home page"""
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template_string(HOME_TEMPLATE)


@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration"""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        message = request.form["message"]

        # Validate input
        if not username or not password or not message:
            return render_template_string(
                REGISTER_TEMPLATE, error="All fields are required"
            )

        if len(username) > 50 or len(message) > 1000:
            return render_template_string(
                REGISTER_TEMPLATE, error="Username or message too long"
            )

        # Hash password
        password_hash = generate_password_hash(password)

        # Insert into database
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
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
    """User login"""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["user_message"] = user["message"]
            return redirect(url_for("dashboard"))
        else:
            return render_template_string(
                LOGIN_TEMPLATE, error="Invalid username or password"
            )

    return render_template_string(LOGIN_TEMPLATE)


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    """User dashboard with cowsay functionality"""
    if "user_id" not in session:
        return redirect(url_for("login"))

    output = None
    if request.method == "POST":
        input_text = request.form["input_text"]

        # VULNERABILITY: Direct command injection possible here
        if input_text:
            # Basic length limit but no proper sanitization
            if len(input_text) > 500:
                output = "Error: Input too long"
            else:
                try:
                    # VULNERABLE: Using shell=True with unsanitized input
                    # This allows command injection via input like: hello; cat /etc/passwd
                    command = f"/usr/games/cowsay {input_text}"
                    result = subprocess.run(
                        command,
                        shell=True,  # VULNERABILITY: shell=True enables command injection
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )

                    if result.returncode == 0:
                        output = result.stdout
                    else:
                        output = f"Error: Command failed\n{result.stderr}"
                except subprocess.TimeoutExpired:
                    output = "Error: Command timeout"
                except FileNotFoundError:
                    output = "Error: Cowsay not available"
                except Exception as e:
                    output = f"Error: {str(e)}"

    return render_template_string(
        DASHBOARD_TEMPLATE,
        username=session["username"],
        user_message=session["user_message"],
        output=output,
    )


@app.route("/logout")
def logout():
    """User logout"""
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    init_db()
    app.run(debug=False, host="0.0.0.0", port=5000)
