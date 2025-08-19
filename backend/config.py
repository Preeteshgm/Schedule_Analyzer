import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Database settings - PostgreSQL
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'schedule_foundation')
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    
    # Build PostgreSQL connection string
    if DB_PASSWORD:
        SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    else:
        # Fallback to SQLite if no PostgreSQL password provided
        SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
        print("⚠️  No PostgreSQL password found in .env - using SQLite")
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # Upload settings
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 209715200))  # 200MB
    
    # CORS settings
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:5173').split(',')
    
    @property 
    def DATABASE_INFO(self):
        """Return database connection info for debugging"""
        if 'postgresql' in self.SQLALCHEMY_DATABASE_URI:
            return {
                'type': 'PostgreSQL',
                'host': self.DB_HOST,
                'port': self.DB_PORT,
                'database': self.DB_NAME,
                'user': self.DB_USER
            }
        else:
            return {
                'type': 'SQLite',
                'file': 'app.db'
            }