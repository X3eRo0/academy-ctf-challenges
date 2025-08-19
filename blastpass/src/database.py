import sqlite3
import hashlib
import os
from contextlib import contextmanager
from config import Config


class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or Config.DATABASE_PATH
        self.init_database()

    def init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    master_password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS vaults (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    master_password TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    UNIQUE(user_id, name)
                )
            """
            )

            try:
                cursor.execute("ALTER TABLE vaults ADD COLUMN master_password TEXT")
            except sqlite3.OperationalError:
                # Column already exists, ignore
                pass

            conn.commit()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
        try:
            yield conn
        finally:
            conn.close()

    def create_user(self, username, master_password):
        salt = os.urandom(32).hex()
        password_hash = hashlib.pbkdf2_hmac(
            "sha256", master_password.encode("utf-8"), bytes.fromhex(salt), 100000
        )

        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO users (username, master_password_hash, salt)
                    VALUES (?, ?, ?)
                """,
                    (username, password_hash.hex(), salt),
                )
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                return None  # Username already exists

    def verify_user(self, username, master_password):
        """Verify user credentials and return user data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, username, master_password_hash, salt
                FROM users WHERE username = ?
            """,
                (username,),
            )

            user = cursor.fetchone()
            if not user:
                return None

            password_hash = hashlib.pbkdf2_hmac(
                "sha256",
                master_password.encode("utf-8"),
                bytes.fromhex(user["salt"]),
                100000,
            )

            if password_hash.hex() == user["master_password_hash"]:
                return dict(user)
            return None

    def get_user_by_id(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            return dict(user) if user else None

    def create_vault(self, user_id, vault_name, filename, master_password):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO vaults (user_id, name, filename, master_password)
                    VALUES (?, ?, ?, ?)
                """,
                    (user_id, vault_name, filename, master_password),
                )
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                return None  # Vault name already exists for this user

    def get_user_vaults(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM vaults WHERE user_id = ?
                ORDER BY created_at DESC
            """,
                (user_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_vault(self, vault_id, user_id=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute(
                    """
                    SELECT * FROM vaults WHERE id = ? AND user_id = ?
                """,
                    (vault_id, user_id),
                )
            else:
                cursor.execute("SELECT * FROM vaults WHERE id = ?", (vault_id,))

            vault = cursor.fetchone()
            return dict(vault) if vault else None

    def delete_vault(self, vault_id, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM vaults WHERE id = ? AND user_id = ?
            """,
                (vault_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
