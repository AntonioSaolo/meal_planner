import argparse
import json
import os

from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash

DEFAULT_TYPE_SEEDS = [
    {"name": "Colazione", "idx": 1},
    {"name": "Spuntino", "idx": 2},
    {"name": "Pranzo", "idx": 3},
    {"name": "Merenda", "idx": 4},
    {"name": "Cena", "idx": 5},
]


def parse_configured_meal_names():
    raw = os.environ.get("MEAL_FIELD_NAMES", "Antonio,Annalisa")
    names = [part.strip() for part in raw.split(",") if part and part.strip()]
    return names or ["Antonio", "Annalisa"]


def should_create_default_admin():
    raw = os.environ.get("CREATE_DEFAULT_ADMIN", "true")
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def seed_default_types(db):
    try:
        from .app.models import Type
    except Exception:
        from app.models import Type

    for item in DEFAULT_TYPE_SEEDS:
        name = item["name"]
        idx = item["idx"]
        existing = Type.query.filter_by(name=name).first()
        if existing:
            if existing.idx != idx:
                existing.idx = idx
            continue
        db.session.add(Type(name=name, idx=idx))

    db.session.commit()
    print("Default meal types ensured")


def create_default_admin_if_needed(db):
    if not should_create_default_admin():
        print("Default admin creation disabled via CREATE_DEFAULT_ADMIN")
        return

    try:
        import os

        try:
            from .app.models import User
        except Exception:
            from app.models import User

        u_name = os.environ.get("DEFAULT_USER_USERNAME")
        u_pass = os.environ.get("DEFAULT_USER_PASSWORD")
        u_email = os.environ.get("DEFAULT_USER_EMAIL")
        if u_name and u_pass:
            exists = User.query.filter_by(username=u_name).first()
            if exists:
                print(f"Default user already exists: {u_name}")
            else:
                user = User(
                    username=u_name,
                    password_hash=generate_password_hash(u_pass),
                    email=u_email,
                )
                db.session.add(user)
                db.session.commit()
                print(f"Default user created: {u_name}")
        else:
            print("DEFAULT_USER_* not set; skipping default user creation")
    except Exception as exc:
        print("Failed to create default user:", exc)


def ensure_meal_columns(db):
    inspector = inspect(db.engine)
    if not inspector.has_table("meals"):
        return

    existing_columns = {column["name"] for column in inspector.get_columns("meals")}
    if "description" not in existing_columns:
        db.session.execute(text("ALTER TABLE meals ADD COLUMN description TEXT"))
        print("Added missing column to meals: description")

    db.session.commit()


def migrate_legacy_meal_columns(row):
    if not isinstance(row, dict):
        return row

    values = dict(row)
    antonio = values.get("antonio")
    annalisa = values.get("annalisa")
    description = values.get("description")

    if antonio is None and annalisa is None:
        return values

    parts = [
        str(part).strip()
        for part in [antonio, annalisa]
        if part is not None and str(part).strip()
    ]
    merged = "\n\n".join(parts) if parts else description
    values["description"] = merged or description
    values["antonio"] = None
    values["annalisa"] = None
    return values


def migrate_legacy_columns(db):
    inspector = inspect(db.engine)
    if not inspector.has_table("meals"):
        return

    columns = {column["name"] for column in inspector.get_columns("meals")}
    if not ({"antonio", "annalisa"} & columns):
        return

    rows = db.session.execute(
        text("SELECT id, description, antonio, annalisa FROM meals")
    ).fetchall()

    for row in rows:
        payload = {}
        if row.description:
            try:
                parsed = json.loads(row.description)
                if isinstance(parsed, dict):
                    payload.update(parsed)
            except Exception:
                pass

        if row.antonio is not None:
            payload.setdefault("Antonio", row.antonio)
        if row.annalisa is not None:
            payload.setdefault("Annalisa", row.annalisa)

        new_description = (
            json.dumps(payload, ensure_ascii=False) if payload else row.description
        )
        db.session.execute(
            text("UPDATE meals SET description = :description WHERE id = :meal_id"),
            {"description": new_description, "meal_id": str(row.id)},
        )

    db.session.execute(text("ALTER TABLE meals DROP COLUMN IF EXISTS antonio"))
    db.session.execute(text("ALTER TABLE meals DROP COLUMN IF EXISTS annalisa"))
    db.session.commit()
    print("Legacy meal columns migrated and removed")


def seed_default_meal_fields(db):
    try:
        from .app.models import MealField
    except Exception:
        from app.models import MealField

    existing_names = {row.name.strip().lower() for row in MealField.query.all()}
    for idx, name in enumerate(parse_configured_meal_names(), start=1):
        normalized = name.strip()
        if not normalized:
            continue
        if normalized.lower() in existing_names:
            continue
        db.session.add(MealField(name=normalized, idx=idx))

    db.session.commit()
    print("Default meal field names ensured")


def ensure_default_data(drop: bool = False):
    try:
        from .app import create_app
        from .app.extensions import db
    except Exception:
        from app import create_app
        from app.extensions import db

    app = create_app()

    with app.app_context():
        try:
            from .app import models  # noqa: F401
        except Exception:
            from app import models  # noqa: F401

        if drop:
            print("--drop provided: dropping existing tables before create_all")
            db.drop_all()

        db.create_all()
        ensure_meal_columns(db)
        migrate_legacy_columns(db)
        seed_default_meal_fields(db)
        print("Database tables ensured (created missing tables)")
        seed_default_types(db)
        create_default_admin_if_needed(db)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed default backend data")
    parser.add_argument(
        "--drop", action="store_true", help="Drop existing tables before creating"
    )
    args = parser.parse_args()
    ensure_default_data(drop=args.drop)
