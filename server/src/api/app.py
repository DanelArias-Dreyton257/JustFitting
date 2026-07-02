"""Flask application factory: wires DB, DAOs, services and blueprints.

``JUSTFITTING_SERVE_CLIENT=true`` additionally serves the static web client
from this same process (see client/src/webapp), so an Android WebView can
point at one port for both the API and the page (Phase 2, docs §13).
"""

from __future__ import annotations

import os
from typing import Optional

from flask import Flask, jsonify
from flask_cors import CORS

from server.src.api.log_routes import log_bp
from server.src.api.metrics_routes import metrics_bp
from server.src.api.projection_routes import projection_bp
from server.src.api.user_routes import user_bp
from server.src.data.db.BodyLogDAO import BodyLogDAO
from server.src.data.db.DB import DB
from server.src.data.db.SessionDAO import SessionDAO
from server.src.data.db.UserDAO import UserDAO
from server.src.services import DemoSeeder
from server.src.services.AuthService import AuthService
from server.src.services.LogManager import LogManager
from server.src.services.UserManager import UserManager


def create_app(config: Optional[dict] = None) -> Flask:
    app = Flask(__name__)
    app.config.update(config or {})

    db_path = app.config.get(
        "DB_PATH", os.environ.get("JUSTFITTING_DB_PATH", "justfitting.db")
    )
    db = DB(db_path)

    user_manager = UserManager(UserDAO(db))
    auth_service = AuthService(SessionDAO(db))
    log_manager = LogManager(BodyLogDAO(db))

    app.extensions["db"] = db
    app.extensions["user_manager"] = user_manager
    app.extensions["auth_service"] = auth_service
    app.extensions["log_manager"] = log_manager

    cors_origins = app.config.get(
        "CORS_ORIGINS", os.environ.get("JUSTFITTING_CORS_ORIGINS", "*")
    )
    CORS(app, resources={r"/api/*": {"origins": cors_origins}})

    app.register_blueprint(user_bp)
    app.register_blueprint(log_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(projection_bp)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    seed_demo = app.config.get(
        "SEED_DEMO", os.environ.get("JUSTFITTING_SEED_DEMO", "false").lower() == "true"
    )
    if seed_demo:
        DemoSeeder.seed_if_empty(user_manager, log_manager)

    if app.config.get(
        "SERVE_CLIENT",
        os.environ.get("JUSTFITTING_SERVE_CLIENT", "false").lower() == "true",
    ):
        _register_client_blueprint(app)

    return app


def _register_client_blueprint(app: Flask) -> None:
    from client.src.Client import client_bp

    app.register_blueprint(client_bp)
