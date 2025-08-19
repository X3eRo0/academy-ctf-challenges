import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "super-secret-key-for-ctf-challenge"
    DATABASE_PATH = "password_manager.db"
    VAULTS_DIR = "vaults"
    MASTER_PASSWORD_MIN_LENGTH = 8
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file upload
