import sys
import click

try:
    from .seed_default_data import ensure_default_data
except Exception:
    from seed_default_data import ensure_default_data


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

    drop_flag = "--drop" in sys.argv
    ensure_default_data(drop=drop_flag)
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
    ensure_default_data(drop=drop)


if __name__ == "__main__":
    import sys

    # allow calling management commands directly: `python src/backend/main.py init-db`
    if len(sys.argv) > 1 and sys.argv[1] == "init-db":
        # call the CLI handler directly when invoked as a script
        init_db()
        sys.exit(0)

    ensure_default_data()
    app.run(host="0.0.0.0", port=int(__import__("os").environ.get("PORT", 8000)))
