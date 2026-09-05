import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "change-me"
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or SECRET_KEY
    # Normalize DATABASE_URL to a SQLAlchemy-compatible dialect name.
    _db_url = os.environ.get("DATABASE_URL") or ""
    if _db_url.startswith("postgres://"):
        # SQLAlchemy expects 'postgresql://' scheme
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url or None
    SQLALCHEMY_TRACK_MODIFICATIONS = False
