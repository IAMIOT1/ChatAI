import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    PORT = int(os.environ.get('PORT', 8888))
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    
    # Database configuration
    DB_DRIVER = os.environ.get('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
    DB_SERVER = os.environ.get('DB_SERVER', 'IAMIOT')
    DB_NAME = os.environ.get('DB_NAME', 'DNU_ChatApp')
    DB_TRUSTED_CONNECTION = os.environ.get('DB_TRUSTED_CONNECTION', 'true').lower() in ['true', '1', 'yes']
    DB_USER = os.environ.get('DB_USER', '')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    
    # Email configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 'yes']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', '1', 'yes']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@chatapp.local')
    
    # OAuth configuration
    GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
    GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
    FACEBOOK_OAUTH_CLIENT_ID = os.environ.get('FACEBOOK_OAUTH_CLIENT_ID')
    FACEBOOK_OAUTH_CLIENT_SECRET = os.environ.get('FACEBOOK_OAUTH_CLIENT_SECRET')
    
    # SocketIO configuration
    SOCKETIO_CORS_ALLOWED_ORIGINS = os.environ.get('SOCKETIO_CORS_ALLOWED_ORIGINS', '*')
    SOCKETIO_MAX_HTTP_BUFFER_SIZE = int(os.environ.get('SOCKETIO_MAX_HTTP_BUFFER_SIZE', '10000000'))
    
    @staticmethod
    def get_database_connection_string():
        """Generate database connection string"""
        conn_str = (
            f"Driver={Config.DB_DRIVER};"
            f"Server={Config.DB_SERVER};"
            f"Database={Config.DB_NAME};"
        )
        
        if Config.DB_TRUSTED_CONNECTION:
            conn_str += "Trusted_Connection=yes;"
        else:
            conn_str += f"UID={Config.DB_USER};PWD={Config.DB_PASSWORD};"
        
        conn_str += "Encrypt=yes;TrustServerCertificate=yes;"
        return conn_str


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    # Override with production-specific settings


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
