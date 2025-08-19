from flask import (
    Flask,
    request,
    jsonify,
    session,
    send_file,
    render_template,
    redirect,
    url_for,
    flash,
)
import io
import csv
import os
import tempfile
import requests
from database import Database
from crypto_client import CSVFormatter
from vaults import VaultManager
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

db = Database()
vault_manager = VaultManager(db)


def require_auth():
    if "user_id" not in session:
        return None
    return db.get_user_by_id(session["user_id"])


def validate_master_password(master_password):
    if len(master_password) < Config.MASTER_PASSWORD_MIN_LENGTH:
        return (
            False,
            f"Master password must be at least {Config.MASTER_PASSWORD_MIN_LENGTH} characters",
        )
    return True, ""


def download_csv_from_url(url):
    try:
        if not url.startswith(("http://", "https://")):
            raise ValueError("Only HTTP and HTTPS URLs are allowed")

        response = requests.get(url, timeout=10, stream=True)
        response.raise_for_status()

        content = b""
        for chunk in response.iter_content(chunk_size=256):
            content += chunk
            if len(content) > 1024:
                raise ValueError("CSV file is too large (maximum 1024 bytes)")

        csv_content = content.decode("utf-8")
        return csv_content

    except requests.exceptions.RequestException as e:
        raise ValueError(f"Failed to download CSV from URL: {str(e)}")
    except UnicodeDecodeError:
        raise ValueError("Downloaded file is not valid UTF-8 text")


@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json()

    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "Username and password required"}), 400

    username = data["username"].strip()
    password = data["password"]

    if not username:
        return jsonify({"error": "Username cannot be empty"}), 400

    valid, error = validate_master_password(password)
    if not valid:
        return jsonify({"error": error}), 400

    user_id = db.create_user(username, password)
    if not user_id:
        return jsonify({"error": "Username already exists"}), 409

    session["user_id"] = user_id
    session["username"] = username

    return (
        jsonify(
            {
                "message": "User registered successfully",
                "user_id": user_id,
                "username": username,
            }
        ),
        201,
    )


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()

    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "Username and password required"}), 400

    username = data["username"].strip()
    password = data["password"]

    user = db.verify_user(username, password)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    session["user_id"] = user["id"]
    session["username"] = user["username"]

    return jsonify(
        {
            "message": "Login successful",
            "user_id": user["id"],
            "username": user["username"],
        }
    )


@app.route("/api/logout", methods=["POST"], endpoint="api_logout")
def api_logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})


@app.route("/api/me", methods=["GET"])
def get_current_user():
    user = require_auth()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    return jsonify({"user_id": user["id"], "username": user["username"]})


@app.route("/api/vaults", methods=["GET"])
def get_vaults():
    user = require_auth()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    vaults = db.get_user_vaults(user["id"])
    return jsonify({"vaults": vaults})


@app.route("/api/vaults", methods=["POST"])
def api_create_vault():
    user = require_auth()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json()
    if not data or "name" not in data or "master_password" not in data:
        return jsonify({"error": "Vault name and master password required"}), 400

    vault_name = data["name"].strip()
    master_password = data["master_password"]
    entries = data.get("entries", [])

    if not vault_name:
        return jsonify({"error": "Vault name cannot be empty"}), 400

    if not db.verify_user(user["username"], master_password):
        return jsonify({"error": "Invalid master password"}), 401

    try:
        vault_id = vault_manager.create_vault(
            user["id"], vault_name, entries, master_password
        )
        return (
            jsonify({"message": "Vault created successfully", "vault_id": vault_id}),
            201,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/vaults/<int:vault_id>/entries", methods=["GET"])
def get_vault_entries(vault_id):
    user = require_auth()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    master_password = request.args.get("master_password")
    if not master_password:
        return jsonify({"error": "Master password required"}), 400

    if not db.verify_user(user["username"], master_password):
        return jsonify({"error": "Invalid master password"}), 401

    try:
        entries = vault_manager.get_vault_entries(vault_id, user["id"], master_password)
        return jsonify({"entries": entries})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/vaults/<int:vault_id>/entries", methods=["POST"])
def add_vault_entries(vault_id):
    user = require_auth()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json()
    if not data or "master_password" not in data or "entries" not in data:
        return jsonify({"error": "Master password and entries required"}), 400

    master_password = data["master_password"]
    entries = data["entries"]

    if not db.verify_user(user["username"], master_password):
        return jsonify({"error": "Invalid master password"}), 401

    try:
        count = vault_manager.add_entries_to_vault(
            vault_id, user["id"], entries, master_password
        )
        return jsonify(
            {"message": f"Added {count} entries to vault", "entries_added": count}
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/vaults/<int:vault_id>", methods=["DELETE"])
def delete_vault(vault_id):
    user = require_auth()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    success = vault_manager.delete_vault(vault_id, user["id"])
    if success:
        return jsonify({"message": "Vault deleted successfully"})
    else:
        return jsonify({"error": "Vault not found or access denied"}), 404


@app.route("/api/vaults/<int:vault_id>/import", methods=["POST"])
def import_csv(vault_id):
    user = require_auth()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    master_password = request.form.get("master_password")

    if not master_password:
        return jsonify({"error": "Master password required"}), 400

    if not db.verify_user(user["username"], master_password):
        return jsonify({"error": "Invalid master password"}), 401

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    try:
        csv_content = file.read().decode("utf-8")
        entries = CSVFormatter.parse_vault_csv(csv_content)

        if not entries:
            return jsonify({"error": "No valid entries found in CSV"}), 400

        count = vault_manager.add_entries_to_vault(
            vault_id, user["id"], entries, master_password
        )
        return jsonify(
            {"message": f"Imported {count} entries from CSV", "entries_imported": count}
        )
    except Exception as e:
        return jsonify({"error": f"Failed to import CSV: {str(e)}"}), 400


@app.route("/api/vaults/<int:vault_id>/download", methods=["POST"])
def download_vault(vault_id):
    data = request.get_json()
    comment = data.get("comment", None) if data else None

    try:
        encrypted_data, filename = vault_manager.download_vault(vault_id, comment)

        file_obj = io.BytesIO(encrypted_data)

        return send_file(
            file_obj,
            as_attachment=True,
            download_name=filename,
            mimetype="application/octet-stream",
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/validate-entry", methods=["POST"])
def api_validate_entry():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Entry data required"}), 400

    url = data.get("url", "")
    username = data.get("username", "")
    password = data.get("password", "")

    valid, error = CSVFormatter.validate_entry(url, username, password)

    return jsonify({"valid": valid, "error": error if not valid else None})


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "password-manager"})


@app.route("/")
def index():
    return render_template("home.html")


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password required", "error")
            return render_template("login.html")

        user = db.verify_user(username, password)
        if not user:
            flash("Invalid credentials", "error")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        flash("Login successful", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register_page():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username:
            flash("Username cannot be empty", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match", "error")
            return render_template("register.html")

        valid, error = validate_master_password(password)
        if not valid:
            flash(error, "error")
            return render_template("register.html")

        user_id = db.create_user(username, password)
        if not user_id:
            flash("Username already exists", "error")
            return render_template("register.html")

        session["user_id"] = user_id
        session["username"] = username
        flash("Account created successfully", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/logout", endpoint="web_logout")
def web_logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for("login_page"))


@app.route("/dashboard")
def dashboard():
    user = require_auth()
    if not user:
        flash("Please login first", "error")
        return redirect(url_for("login_page"))

    vaults = db.get_user_vaults(user["id"])
    return render_template("dashboard.html", vaults=vaults)


@app.route("/create-vault", methods=["GET", "POST"])
def create_vault_page():
    user = require_auth()
    if not user:
        flash("Please login first", "error")
        return redirect(url_for("login_page"))

    if request.method == "POST":
        vault_name = request.form.get("vault_name", "").strip()
        master_password = request.form.get("master_password", "")

        if not vault_name:
            flash("Vault name cannot be empty", "error")
            return render_template("create_vault.html")

        if not master_password:
            flash("Master password is required", "error")
            return render_template("create_vault.html")

        entries = []
        for i in range(1, 4):  # Support up to 3 entries
            url = request.form.get(f"url_{i}", "").strip()
            username = request.form.get(f"username_{i}", "").strip()
            password = request.form.get(f"password_{i}", "").strip()

            if url and username and password:
                valid, error = CSVFormatter.validate_entry(url, username, password)
                if not valid:
                    flash(f"Entry {i}: {error}", "error")
                    return render_template("create_vault.html")
                entries.append({"url": url, "username": username, "password": password})

        try:
            vault_id = vault_manager.create_vault(
                user["id"], vault_name, entries, master_password
            )
            flash(f'Vault "{vault_name}" created successfully', "success")
            return redirect(url_for("vault_view", vault_id=vault_id))
        except ValueError as e:
            flash(str(e), "error")
            return render_template("create_vault.html")

    return render_template("create_vault.html")


@app.route("/vault/<int:vault_id>", endpoint="vault_view")
def vault_view(vault_id):
    user = require_auth()
    if not user:
        flash("Please login first", "error")
        return redirect(url_for("login_page"))

    vault = db.get_vault(vault_id, user["id"])
    if not vault:
        flash("Vault not found or access denied", "error")
        return redirect(url_for("dashboard"))

    return render_template("vault_view.html", vault=vault, entries=None)


@app.route("/vault/<int:vault_id>", methods=["POST"], endpoint="vault_unlock")
def vault_unlock(vault_id):
    user = require_auth()
    if not user:
        flash("Please login first", "error")
        return redirect(url_for("login_page"))

    vault = db.get_vault(vault_id, user["id"])
    if not vault:
        flash("Vault not found or access denied", "error")
        return redirect(url_for("dashboard"))

    master_password = request.form.get("master_password", "")
    if not master_password:
        flash("Master password required", "error")
        return render_template("vault_view.html", vault=vault, entries=None)

    try:
        entries = vault_manager.get_vault_entries(vault_id, user["id"], master_password)
        return render_template("vault_view.html", vault=vault, entries=entries)
    except ValueError as e:
        flash(str(e), "error")
        return render_template("vault_view.html", vault=vault, entries=None)


@app.route("/vault/<int:vault_id>/add", methods=["GET", "POST"])
def add_entries_page(vault_id):
    user = require_auth()
    if not user:
        flash("Please login first", "error")
        return redirect(url_for("login_page"))

    vault = db.get_vault(vault_id, user["id"])
    if not vault:
        flash("Vault not found or access denied", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        master_password = request.form.get("master_password", "")

        if not master_password:
            flash("Master password required", "error")
            return render_template("add_entries.html", vault=vault)

        entries = []
        for i in range(1, 4):
            url = request.form.get(f"url_{i}", "").strip()
            username = request.form.get(f"username_{i}", "").strip()
            password = request.form.get(f"password_{i}", "").strip()

            if url and username and password:
                valid, error = CSVFormatter.validate_entry(url, username, password)
                if not valid:
                    flash(f"Entry {i}: {error}", "error")
                    return render_template("add_entries.html", vault=vault)
                entries.append({"url": url, "username": username, "password": password})

        if not entries:
            flash("No valid entries provided", "error")
            return render_template("add_entries.html", vault=vault)

        try:
            count = vault_manager.add_entries_to_vault(
                vault_id, user["id"], entries, master_password
            )
            flash(f"Added {count} entries to vault", "success")
            return redirect(url_for("vault_view", vault_id=vault_id))
        except ValueError as e:
            flash(str(e), "error")
            return render_template("add_entries.html", vault=vault)

    return render_template("add_entries.html", vault=vault)


@app.route("/vault/<int:vault_id>/delete", methods=["POST"])
def delete_vault_page(vault_id):
    user = require_auth()
    if not user:
        flash("Please login first", "error")
        return redirect(url_for("login_page"))

    success = vault_manager.delete_vault(vault_id, user["id"])
    if success:
        flash("Vault deleted successfully", "success")
    else:
        flash("Vault not found or access denied", "error")

    return redirect(url_for("dashboard"))


@app.route("/vault/<int:vault_id>/download", methods=["GET", "POST"])
def download_vault_page(vault_id):
    user = require_auth()
    if not user:
        flash("Please login first", "error")
        return redirect(url_for("login_page"))

    vault = db.get_vault(vault_id, user["id"])
    if not vault:
        flash("Vault not found or access denied", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        master_password = request.form.get("master_password", "")
        comment = request.form.get("comment", "")

        try:
            encrypted_data, filename = vault_manager.download_vault(vault_id, comment)
            file_obj = io.BytesIO(encrypted_data)
            return send_file(
                file_obj,
                as_attachment=True,
                download_name=filename,
                mimetype="application/octet-stream",
            )
        except ValueError as e:
            flash(str(e), "error")
            return render_template("download_vault.html", vault=vault)

    return render_template("download_vault.html", vault=vault)


@app.route("/vault/<int:vault_id>/import", methods=["GET", "POST"])
def import_to_vault_page(vault_id):
    user = require_auth()
    if not user:
        flash("Please login first", "error")
        return redirect(url_for("login_page"))

    vault = db.get_vault(vault_id, user["id"])
    if not vault:
        flash("Vault not found or access denied", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        master_password = request.form.get("master_password", "")
        import_method = request.form.get("import_method", "file")

        if not master_password:
            flash("Master password required", "error")
            return render_template("import_csv.html", vault=vault)

        try:
            if import_method == "url":
                csv_url = request.form.get("csv_url", "").strip()
                if not csv_url:
                    flash("CSV URL required", "error")
                    return render_template("import_csv.html", vault=vault)

                csv_content = download_csv_from_url(csv_url)
            else:
                if "file" not in request.files:
                    flash("No file uploaded", "error")
                    return render_template("import_csv.html", vault=vault)

                file = request.files["file"]
                if file.filename == "":
                    flash("No file selected", "error")
                    return render_template("import_csv.html", vault=vault)

                csv_content = file.read().decode("utf-8")

            entries = CSVFormatter.parse_vault_csv(csv_content)

            if not entries:
                flash("No valid entries found in CSV", "error")
                return render_template("import_csv.html", vault=vault)

            count = vault_manager.add_entries_to_vault(
                vault_id, user["id"], entries, master_password
            )
            flash(f"Imported {count} entries from CSV", "success")
            return redirect(url_for("vault_view", vault_id=vault_id))
        except Exception as e:
            flash(f"Failed to import CSV: {str(e)}", "error")
            return render_template("import_csv.html", vault=vault)

    return render_template("import_csv.html", vault=vault)


@app.route("/import-csv", methods=["GET", "POST"])
def import_csv_page():
    user = require_auth()
    if not user:
        flash("Please login first", "error")
        return redirect(url_for("login_page"))

    if request.method == "POST":
        vault_name = request.form.get("vault_name", "").strip()
        master_password = request.form.get("master_password", "")
        import_method = request.form.get("import_method", "file")

        if not vault_name:
            flash("Vault name cannot be empty", "error")
            return render_template("import_csv.html")

        if not master_password:
            flash("Master password required", "error")
            return render_template("import_csv.html")

        try:
            if import_method == "url":
                csv_url = request.form.get("csv_url", "").strip()
                if not csv_url:
                    flash("CSV URL required", "error")
                    return render_template("import_csv.html")

                csv_content = download_csv_from_url(csv_url)
            else:
                if "file" not in request.files:
                    flash("No file uploaded", "error")
                    return render_template("import_csv.html")

                file = request.files["file"]
                if file.filename == "":
                    flash("No file selected", "error")
                    return render_template("import_csv.html")

                csv_content = file.read().decode("utf-8")

            entries = CSVFormatter.parse_vault_csv(csv_content)

            if not entries:
                flash("No valid entries found in CSV", "error")
                return render_template("import_csv.html")

            vault_id = vault_manager.create_vault(
                user["id"], vault_name, entries, master_password
            )
            flash(
                f'Created vault "{vault_name}" with {len(entries)} entries', "success"
            )
            return redirect(url_for("vault_view", vault_id=vault_id))
        except Exception as e:
            flash(f"Failed to import CSV: {str(e)}", "error")
            return render_template("import_csv.html")

    return render_template("import_csv.html")


@app.route("/browse-vaults")
def browse_vaults():
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT v.id, v.name, v.created_at, u.username
            FROM vaults v
            JOIN users u ON v.user_id = u.id
            ORDER BY v.created_at DESC
        """
        )
        vaults = [dict(row) for row in cursor.fetchall()]

    return render_template("browse_vaults.html", vaults=vaults)


@app.route("/download/<int:vault_id>", methods=["GET", "POST"])
def public_download_vault(vault_id):
    vault = db.get_vault(vault_id)
    if not vault:
        flash("Vault not found", "error")
        return redirect(url_for("browse_vaults"))

    if request.method == "POST":
        master_password = request.form.get("master_password", "")
        comment = request.form.get("comment", "")

        try:
            encrypted_data, filename = vault_manager.download_vault(vault_id, comment)
            file_obj = io.BytesIO(encrypted_data)
            return send_file(
                file_obj,
                as_attachment=True,
                download_name=filename,
                mimetype="application/octet-stream",
            )
        except ValueError as e:
            flash(str(e), "error")
            return render_template("download_vault.html", vault_id=vault_id)

    return render_template("download_vault.html", vault_id=vault_id)


# Error handlers
@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "File too large"}), 413


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3333, threaded=True, use_reloader=False)
