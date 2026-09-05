import os
from flask import Flask, request
from .extensions import db, jwt
from .config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # if DATABASE_URL not set in env, build it from individual POSTGRES_* vars
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        user = os.environ.get("POSTGRES_USER", "meal_user")
        password = os.environ.get("POSTGRES_PASSWORD", "meal_password")
        host = os.environ.get("POSTGRES_HOST", "db")
        port = os.environ.get("POSTGRES_PORT", "5432")
        dbname = os.environ.get("POSTGRES_DB", "meal_db")
        app.config["SQLALCHEMY_DATABASE_URI"] = (
            f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
        )

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

    db.init_app(app)
    jwt.init_app(app)

    # register routes (import here to avoid circular imports at module import time)
    from .routes import bp as routes_bp

    app.register_blueprint(routes_bp)

    return app
