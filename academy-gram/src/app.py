import os
import sqlite3
import random
import string
import hashlib
from datetime import datetime, timedelta
from flask import (
    Flask,
    request,
    session,
    redirect,
    url_for,
    render_template,
    g,
    flash,
    abort,
    make_response,
    send_from_directory,
    Response,
)

# --- App Conf ---
app = Flask(__name__)
app.config.update(
    dict(
        DATABASE=os.path.join(app.root_path, "academygram.db"),
        SECRET_KEY="a_super_static_secret_key_for_ctf",
    )
)


# --- Database ---
def get_db():
    if not hasattr(g, "sqlite_db"):
        g.sqlite_db = sqlite3.connect(app.config["DATABASE"])
        g.sqlite_db.row_factory = sqlite3.Row
    return g.sqlite_db


@app.teardown_appcontext
def close_db(error):
    if hasattr(g, "sqlite_db"):
        g.sqlite_db.close()


def init_db():
    db = get_db()
    with app.open_resource("schema.sql", mode="r") as f:
        db.cursor().executescript(f.read())
    db.commit()


@app.cli.command("initdb")
def initdb_command():
    """Initializes the database."""
    init_db()
    print("Initialized the database.")


# --- Models ---
class User:
    @staticmethod
    def find_by_username(username):
        db = get_db()
        cur = db.execute("SELECT * FROM users WHERE username = ?", [username])
        return cur.fetchone()

    @staticmethod
    def find_by_id(user_id):
        db = get_db()
        cur = db.execute("SELECT * FROM users WHERE user_id = ?", [user_id])
        return cur.fetchone()

    @staticmethod
    def create(username, password):
        db = get_db()
        db.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)", [username, password]
        )
        db.commit()


class Post:
    @staticmethod
    def get_all():
        db = get_db()
        cur = db.execute(
            "SELECT p.content, p.image_path, u.username FROM posts p JOIN users u ON p.user_id = u.user_id WHERE p.is_private = 0 ORDER BY p.pub_date DESC"
        )
        return cur.fetchall()

    @staticmethod
    def get_for_user(user_id):
        db = get_db()
        cur = db.execute(
            "SELECT content, image_path, is_private FROM posts WHERE user_id = ? ORDER BY pub_date DESC",
            [user_id],
        )
        return cur.fetchall()

    @staticmethod
    def create(user_id, content, image_path=None, is_private=False):
        db = get_db()
        db.execute(
            "INSERT INTO posts (user_id, content, image_path, is_private) VALUES (?, ?, ?, ?)",
            [user_id, content, image_path, is_private],
        )
        db.commit()


# --- Routes ---
@app.before_request
def before_request():
    g.user = None
    if "user_id" in session:
        g.user = User.find_by_id(session["user_id"])


@app.route("/")
def timeline():
    if not g.user:
        return redirect(url_for("login"))
    posts = Post.get_all()
    return render_template("timeline.html", posts=posts)


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("timeline"))
    error = None
    if request.method == "POST":
        if not request.form["username"]:
            error = "You have to enter a username"
        elif not request.form["password"]:
            error = "You have to enter a password"
        elif User.find_by_username(request.form["username"]) is not None:
            error = "The username is already taken"
        else:
            User.create(request.form["username"], request.form["password"])
            flash("You were successfully registered and can login now")
            return redirect(url_for("login"))
    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("timeline"))
    error = None
    if request.method == "POST":
        user = User.find_by_username(request.form["username"])
        if user is None:
            error = "Invalid username"
        elif user["password"] != request.form["password"]:
            error = "Invalid password"
        else:
            flash("You were logged in")
            session["user_id"] = user["user_id"]
            return redirect(url_for("timeline"))
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    flash("You were logged out")
    session.pop("user_id", None)
    return redirect(url_for("login"))


from werkzeug.utils import secure_filename

# ... (rest of the imports)

# --- App Conf ---
app.config.update(
    dict(
        DATABASE=os.path.join(app.root_path, "academygram.db"),
        SECRET_KEY="a_super_static_secret_key_for_ctf",
        UPLOAD_FOLDER=os.path.join(app.root_path, "static/posts"),
        ALLOWED_EXTENSIONS={"png", "jpg", "jpeg", "gif"},
    )
)

# ... (rest of the app)


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
    )

    # ... (inside Post class)
    @staticmethod
    def create(user_id, content, image_path=None, is_private=False):
        db = get_db()
        db.execute(
            "INSERT INTO posts (user_id, content, image_path, is_private) VALUES (?, ?, ?, ?)",
            [user_id, content, image_path, is_private],
        )
        db.commit()


# ... (rest of the app)


@app.route("/add_post", methods=["POST"])
def add_post():
    if not g.user:
        abort(401)

    content = request.form.get("content")
    is_private = "is_private" in request.form
    image_path = None

    if "image" in request.files:
        file = request.files["image"]
        if file and file.filename != "" and allowed_file(file.filename):
            try:
                filename = secure_filename(file.filename)
                # To avoid overwrites, prepend with user_id and a random string
                unique_filename = (
                    f"{g.user['user_id']}_{os.urandom(4).hex()}_{filename}"
                )
                save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)

                # Ensure the upload directory exists
                os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

                file.save(save_path)
                image_path = os.path.join("static/posts", unique_filename)
            except Exception as e:
                flash(f"Error uploading image: {str(e)}")
                return redirect(url_for("timeline"))

    if content or image_path:
        Post.create(session["user_id"], content, image_path, is_private)
        flash("Your post was successfully added")

    return redirect(url_for("timeline"))


@app.route("/profile")
def profile():
    if not g.user:
        return redirect(url_for("login"))

    # Load current user's profile
    posts = Post.get_for_user(g.user["user_id"])
    return render_template("profile.html", posts=posts, profile_user=g.user)


class PasswordReset:
    @staticmethod
    def generate_time_based_code():
        import time

        current_minute = int(time.time() // 60)
        rng = random.Random()
        rng.seed(current_minute)
        code = str(rng.randint(1000, 9999)).zfill(4)
        return code

    @staticmethod
    def create(user_id):
        db = get_db()
        code = PasswordReset.generate_time_based_code()
        expires = datetime.utcnow() + timedelta(minutes=30)

        db.execute("DELETE FROM password_resets WHERE user_id = ?", [user_id])
        db.execute(
            "INSERT INTO password_resets (user_id, reset_code, expires_at) VALUES (?, ?, ?)",
            [user_id, code, expires],
        )
        db.commit()
        return code

    @staticmethod
    def find(user_id, code):
        db = get_db()
        cur = db.execute(
            "SELECT * FROM password_resets WHERE user_id = ? AND reset_code = ? ORDER BY expires_at DESC LIMIT 1",
            [user_id, code],
        )
        return cur.fetchone()

    @staticmethod
    def update_password(user_id, password):
        db = get_db()
        db.execute(
            "UPDATE users SET password = ? WHERE user_id = ?", [password, user_id]
        )
        db.commit()
        db.execute("DELETE FROM password_resets WHERE user_id = ?", [user_id])
        db.commit()


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    error = None
    if request.method == "POST":
        user = User.find_by_username(request.form["username"])
        if user:
            code = PasswordReset.create(user["user_id"])
            return redirect(url_for("reset_password", username=user["username"]))
        else:
            error = "User not found"
    return render_template("forgot_password.html", error=error)


@app.route("/reset_password/<username>", methods=["GET", "POST"])
def reset_password(username):
    user = User.find_by_username(username)
    if not user:
        abort(404)

    error = None
    if request.method == "POST":
        code = request.form["code"]
        new_password = request.form["new_password"]

        reset_token = PasswordReset.find(user["user_id"], code)

        if not reset_token:
            error = "Invalid code."
        elif (
            datetime.strptime(reset_token["expires_at"], "%Y-%m-%d %H:%M:%S.%f")
            < datetime.utcnow()
        ):
            error = "Reset code has expired."
        else:
            PasswordReset.update_password(user["user_id"], new_password)
            flash("Your password has been successfully reset.")
            return redirect(url_for("login"))

    return render_template("reset_password.html", username=username, error=error)


@app.route("/get_code")
def get_code():
    """Get current time-based reset code"""
    if not g.user:
        return redirect(url_for("login"))

    code = PasswordReset.generate_time_based_code()
    return {"username": g.user["username"], "current_code": code}


@app.route("/interests")
def interests():
    if not g.user:
        return redirect(url_for("login"))

    user_id = request.args.get("user_id", g.user["user_id"])
    user_of_interest = User.find_by_id(user_id)

    if not user_of_interest:
        abort(404)

    return render_template(
        "interests.html", user_of_interest=user_of_interest, current_user=g.user
    )


@app.route("/update_interests", methods=["POST"])
def update_user_interests():
    if not g.user:
        return redirect(url_for("login"))

    interests = request.form.get("interests", "")

    db = get_db()
    db.execute(
        "UPDATE users SET interests = ? WHERE user_id = ?",
        [interests, g.user["user_id"]],
    )
    db.commit()

    flash("Your interests have been updated")
    return redirect(url_for("interests"))


@app.route("/uploads/<path:filename>")
def view_upload(filename):
    return redirect(url_for("view_file", filename=filename))


@app.route("/view_file")
def view_file():
    filename = request.args.get("filename", "default.png")

    try:
        base_path = os.path.dirname(__file__)
        file_path = os.path.join(base_path, "uploads", filename)

        if "uploads" not in request.args:
            return "File not found in uploads directory.", 400

        with open(file_path, "r") as f:
            content = f.read()

        return Response(content, mimetype="text/plain")

    except Exception as e:
        return str(e), 404
