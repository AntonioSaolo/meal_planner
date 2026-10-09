import os
from pathlib import Path
from dotenv import load_dotenv


def find_project_root():
    # assume this file is at <project>/src/brackend/app/config.py
    p = Path(__file__).resolve()
    # parents: 0=app,1=brackend,2=src,3=project
    proj = p.parents[3]
    return proj


PROJECT_ROOT = find_project_root()
ENV_PATH = PROJECT_ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=str(ENV_PATH))


def normalize_database_url(raw_url):
    if raw_url and raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return raw_url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "change-me"
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or SECRET_KEY
    SQLALCHEMY_DATABASE_URI = normalize_database_url(os.environ.get("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    @staticmethod
    def build_database_url():
        """Build DATABASE_URL from POSTGRES_* env vars or .env file values."""
        user = os.environ.get("POSTGRES_USER", "meal_user")
        password = os.environ.get("POSTGRES_PASSWORD", "meal_password")
        host = os.environ.get("POSTGRES_HOST", "db")
        port = os.environ.get("POSTGRES_PORT", "5432")
        dbname = os.environ.get("POSTGRES_DB", "meal_db")
        return normalize_database_url(
            f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
        )
