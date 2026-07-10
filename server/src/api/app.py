"""Flask application factory: wires DB, DAOs, services and blueprints."""

from __future__ import annotations

import os
from typing import Optional

from flask import Flask, jsonify
from flask_cors import CORS

from server.src.api.activity_goal_routes import activity_goal_bp
from server.src.api.alerts_routes import alerts_bp
from server.src.api.body_measurement_routes import body_measurement_bp
from server.src.api.log_routes import log_bp
from server.src.api.metrics_routes import metrics_bp
from server.src.api.plan_routes import plan_bp
from server.src.api.projection_routes import projection_bp
from server.src.api.settings_routes import settings_bp
from server.src.api.user_routes import user_bp
from server.src.data.db.ActivityGoalDAO import ActivityGoalDAO
from server.src.data.db.AlertLogDAO import AlertLogDAO
from server.src.data.db.AuditLogDAO import AuditLogDAO
from server.src.data.db.BodyLogDAO import BodyLogDAO
from server.src.data.db.BodyMeasurementDAO import BodyMeasurementDAO
from server.src.data.db.DB import DB
from server.src.data.db.EngineSettingsDAO import EngineSettingsDAO
from server.src.data.db.GoalPlanDAO import GoalPlanDAO
from server.src.data.db.MetricsSnapshotDAO import MetricsSnapshotDAO
from server.src.data.db.ProjectionDAO import ProjectionDAO
from server.src.data.db.SessionDAO import SessionDAO
from server.src.data.db.UserDAO import UserDAO
from server.src.services import DemoSeeder
from server.src.services.ActivityGoalManager import ActivityGoalManager
from server.src.services.AuthService import AuthService
from server.src.services.BodyMeasurementManager import BodyMeasurementManager
from server.src.services.EngineSettingsManager import EngineSettingsManager
from server.src.services.GoalPlanManager import GoalPlanManager
from server.src.services.LogManager import LogManager
from server.src.services.MetricsCache import MetricsCache
from server.src.services.PasswordResetService import PasswordResetService
from server.src.services.ProjectionService import ProjectionService
from server.src.services.UserManager import UserManager


def create_app(config: Optional[dict] = None) -> Flask:
    app = Flask(__name__)
    app.config.update(config or {})

    db_path = app.config.get(
        "DB_PATH", os.environ.get("JUSTFITTING_DB_PATH", "justfitting.db")
    )
    db = DB(db_path)

    audit_log_dao = AuditLogDAO(db)
    alert_log_dao = AlertLogDAO(db)
    user_dao = UserDAO(db)
    session_dao = SessionDAO(db)
    metrics_cache = MetricsCache(MetricsSnapshotDAO(db))
    goal_plan_manager = GoalPlanManager(
        GoalPlanDAO(db), audit_log_dao=audit_log_dao, metrics_cache=metrics_cache
    )
    engine_settings_manager = EngineSettingsManager(
        EngineSettingsDAO(db), audit_log_dao=audit_log_dao, metrics_cache=metrics_cache
    )
    user_manager = UserManager(user_dao, goal_plan_manager, audit_log_dao=audit_log_dao)
    auth_service = AuthService(session_dao)
    log_manager = LogManager(
        BodyLogDAO(db), audit_log_dao=audit_log_dao, metrics_cache=metrics_cache
    )
    measurement_manager = BodyMeasurementManager(
        BodyMeasurementDAO(db), audit_log_dao=audit_log_dao, metrics_cache=metrics_cache
    )
    projection_service = ProjectionService(ProjectionDAO(db))
    activity_goal_manager = ActivityGoalManager(
        ActivityGoalDAO(db), audit_log_dao=audit_log_dao
    )

    password_reset_service = PasswordResetService(
        user_dao, session_dao, audit_log_dao=audit_log_dao
    )

    app.extensions["db"] = db
    app.extensions["user_manager"] = user_manager
    app.extensions["auth_service"] = auth_service
    app.extensions["log_manager"] = log_manager
    app.extensions["body_measurement_manager"] = measurement_manager
    app.extensions["goal_plan_manager"] = goal_plan_manager
    app.extensions["engine_settings_manager"] = engine_settings_manager
    app.extensions["audit_log_dao"] = audit_log_dao
    app.extensions["alert_log_dao"] = alert_log_dao
    app.extensions["metrics_cache"] = metrics_cache
    app.extensions["projection_service"] = projection_service
    app.extensions["password_reset_service"] = password_reset_service
    app.extensions["activity_goal_manager"] = activity_goal_manager

    cors_origins = app.config.get(
        "CORS_ORIGINS", os.environ.get("JUSTFITTING_CORS_ORIGINS", "*")
    )
    CORS(app, resources={r"/api/*": {"origins": cors_origins}})

    app.register_blueprint(user_bp)
    app.register_blueprint(log_bp)
    app.register_blueprint(body_measurement_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(projection_bp)
    app.register_blueprint(plan_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(activity_goal_bp)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    seed_demo = app.config.get(
        "SEED_DEMO", os.environ.get("JUSTFITTING_SEED_DEMO", "false").lower() == "true"
    )
    if seed_demo:
        DemoSeeder.seed_if_empty(
            user_manager,
            log_manager,
            goal_plan_manager,
            engine_settings_manager,
            measurement_manager,
        )

    return app
