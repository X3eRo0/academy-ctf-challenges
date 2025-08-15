import os

class Config:
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super-secret-key-for-ctf-challenge'
    
    # Database settings
    DATABASE_PATH = 'password_manager.db'
    
    # Vault storage settings
    VAULTS_DIR = 'vaults'
    
    # Security settings
    MASTER_PASSWORD_MIN_LENGTH = 8
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file upload
