from flask import Flask, request, send_from_directory
from .config import Config
from .extensions import db, jwt
from sqlalchemy import text
from pathlib import Path


def create_app():
    project_root = Path(__file__).resolve().parents[3]
    frontend_build_dir = project_root / "src" / "backend" / "static"
    app = Flask(__name__, static_folder=str(frontend_build_dir), static_url_path="")
    app.config.from_object(Config)

    # ensure DATABASE_URL is available (config handles loading .env)
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = Config.build_database_url()

    def set_cors_headers(response):
        origin = request.headers.get("Origin")
        response.headers["Access-Control-Allow-Origin"] = origin or "*"
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization, Origin, Accept, X-Requested-With"
        )
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, DELETE, PUT, OPTIONS"
        )
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
        return response

    @app.after_request
    def add_cors_headers(response):
        return set_cors_headers(response)

    @app.route("/<path:path>", methods=["OPTIONS"])
    def handle_options(path):
        response = app.make_response("")
        response.status_code = 204
        return set_cors_headers(response)

    if frontend_build_dir.exists():

        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def serve_frontend(path):
            if path and (frontend_build_dir / path).exists():
                return send_from_directory(str(frontend_build_dir), path)
            return send_from_directory(str(frontend_build_dir), "index.html")

    db.init_app(app)
    jwt.init_app(app)

    # fail-fast: verify DB connectivity at startup so the app doesn't silently run
    # when the database is down. This makes failures visible immediately.
    try:
        with app.app_context():
            # a lightweight check that opens a connection and issues a trivial query
            # SQLAlchemy requires textual SQL to be wrapped with text(...)
            db.session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - environment dependent
        # log and re-raise so the process exits instead of starting a broken app
        app.logger.exception("Database connectivity check failed during startup")
        raise

    # Note: default user creation has been removed from app startup.
    # Use the provided CLI script `src/backend/scripts/create_user.py` to add users.

    # register blueprints
    from .routes import bp as routes_bp

    app.register_blueprint(routes_bp)

    return app
