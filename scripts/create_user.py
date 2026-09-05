#!/usr/bin/env python3
"""Standalone script to create a user in the database.

This script is intentionally independent from the application codebase
and talks to the database directly via `psycopg2`.

Usage examples:
  DATABASE_URL=postgresql://meal_user:pass@localhost:5432/meal_db \
    python scripts/create_user.py --username admin --password secret --email admin@example.com

Options:
  --database-url override DATABASE_URL env
  --create-table  create a minimal `users` table if it doesn't exist (development convenience)

Note: The script stores a salted password hash using Werkzeug's `generate_password_hash`.
"""

import os
import argparse
import uuid
import os
from getpass import getpass
import argparse
import psycopg2
from psycopg2 import sql
from psycopg2.extras import register_uuid
from pathlib import Path
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash


def create_users_table_if_missing(conn):
    """Create a minimal users table compatible with the app models.
    Uses TEXT for password_hash to avoid truncation of modern hash formats.
    """
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id uuid PRIMARY KEY,
            username varchar(40) UNIQUE NOT NULL,
            password_hash text NOT NULL,
            email varchar(255),
            avatar_url varchar(512)
        )
        """)
    conn.commit()
    # If the table already existed with a limited varchar password_hash,
    # ensure the column type can hold modern hashes by converting to TEXT.
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'password_hash'
            """)
        row = cur.fetchone()
        if row and row[0] is not None:
            # column has a max length (e.g. varchar(128)), change to text
            cur.execute("ALTER TABLE users ALTER COLUMN password_hash TYPE text")
            conn.commit()
        cur.close()
    except Exception:
        # best-effort: if we can't inspect/alter, continue and let inserts report errors
        try:
            cur.close()
        except Exception:
            pass


def user_exists(conn, username):
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = %s", (username,))
    row = cur.fetchone()
    cur.close()
    return row[0] if row else None


def insert_user(conn, username, password, email=None):
    register_uuid()
    cur = conn.cursor()
    user_id = uuid.uuid4()
    pw_hash = generate_password_hash(password)
    try:
        cur.execute(
            "INSERT INTO users (id, username, password_hash, email, avatar_url) VALUES (%s, %s, %s, %s, %s)",
            (user_id, username, pw_hash, email, None),
        )
        conn.commit()
        print(f"Created user '{username}' with id {user_id}")
    except psycopg2.IntegrityError as e:
        conn.rollback()
        print("Failed to create user: integrity error", e)
        raise
    finally:
        cur.close()


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Create a user directly in the DB (standalone script)"
    )
    p.add_argument("--username", required=False)
    p.add_argument("--password", required=False)
    p.add_argument("--email", required=False)
    p.add_argument(
        "--database-url",
        required=False,
        help="Postgres DSN (overrides DATABASE_URL env)",
    )
    p.add_argument(
        "--create-table", action="store_true", help="Create users table if missing"
    )

    args = p.parse_args(argv)

    # Load .env from project root if present
    here = Path(__file__).resolve().parent
    project_root = here.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not provided; set env or use --database-url")
        sys.exit(2)

    username = args.username or os.environ.get("DEFAULT_USER_USERNAME")
    if not username:
        username = input("username: ")

    password = args.password or os.environ.get("DEFAULT_USER_PASSWORD")
    if not password:
        password = getpass("password: ")

    email = args.email or os.environ.get("DEFAULT_USER_EMAIL")

    # Normalize postgres scheme
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    conn = psycopg2.connect(database_url)

    try:
        if args.create_table:
            create_users_table_if_missing(conn)

        exists = user_exists(conn, username)
        if exists:
            print(f"User '{username}' already exists (id={exists}). Aborting.")
            return

        insert_user(conn, username, password, email=email)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
