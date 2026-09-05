import sys
import click

DEFAULT_TYPE_SEEDS = [
    {"name": "Colazione", "idx": 1},
    {"name": "Spuntino", "idx": 2},
    {"name": "Pranzo", "idx": 3},
    {"name": "Merenda", "idx": 4},
    {"name": "Cena", "idx": 5},
]


def seed_default_types():
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


# If invoked directly as a script with the `init-db` arg, handle it before
# importing/instantiating the Flask app so Click/Flask CLI doesn't consume args.
if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "init-db":
    # try package import first, then fallback to script-relative imports
    try:
        from .app import create_app
        from .app.extensions import db
        from . import app as app_module
    except Exception:
        from app import create_app
        from app.extensions import db
        import app as app_module

    app = create_app()

    # ensure models are imported so their Table objects are registered
    try:
        from .app import models  # when executed as package
    except Exception:
        from app import models  # fallback when executed as a script

    # support optional --drop flag when running as a script
    drop_flag = "--drop" in sys.argv

    with app.app_context():
        existing = list(db.metadata.tables.keys())
        print("Existing metadata tables before create_all:", existing)

        if drop_flag:
            print("--drop provided: dropping existing tables before create_all")
            db.drop_all()

        # create any missing tables (without dropping by default)
        db.create_all()

        created = list(db.metadata.tables.keys())
        print("Metadata tables after create_all:", created)
        if drop_flag:
            print("Database tables recreated (dropped + created)")
        else:
            print("Database tables ensured (created missing tables)")

        # ensure default meal types exist before the app is used
        seed_default_types()

        # optionally create a default user if env vars are present
        try:
            import os
            from werkzeug.security import generate_password_hash

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

    sys.exit(0)


try:
    # preferred when executed as a package (python -m brackend.main)
    from .app import create_app
    from .app.extensions import db
except Exception:
    # fallback when executed directly as a script (python src/brackend/main.py)
    from app import create_app
    from app.extensions import db


app = create_app()


@app.cli.command("init-db")
@click.option("--drop", is_flag=True, help="Drop existing tables before creating")
def init_db(drop: bool):
    """Create database tables."""
    with app.app_context():
        # ensure models are imported so their Table objects are registered
        try:
            from .app import models  # when executed as package
        except Exception:
            from app import models  # fallback when executed as a script

        # show current metadata tables for diagnostics
        existing = list(db.metadata.tables.keys())
        print("Existing metadata tables before create_all:", existing)

        if drop:
            print("--drop provided: dropping existing tables before create_all")
            db.drop_all()

        # create any missing tables (without dropping by default)
        db.create_all()

        created = list(db.metadata.tables.keys())
        print("Metadata tables after create_all:", created)
        if drop:
            print("Database tables recreated (dropped + created)")
        else:
            print("Database tables ensured (created missing tables)")

        # ensure default meal types exist before the app is used
        seed_default_types()

        # optionally create a default user if env vars are present
        try:
            import os
            from werkzeug.security import generate_password_hash

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


if __name__ == "__main__":
    import sys

    # allow calling management commands directly: `python src/backend/main.py init-db`
    if len(sys.argv) > 1 and sys.argv[1] == "init-db":
        # call the CLI handler directly when invoked as a script
        init_db()
        sys.exit(0)

    app.run(host="0.0.0.0", port=int(__import__("os").environ.get("PORT", 8000)))
