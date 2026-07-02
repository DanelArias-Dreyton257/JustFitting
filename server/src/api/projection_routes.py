"""Forecast route: extrapolate future weekly rows from real logs."""

from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, current_app, g, jsonify, request

from server.src.api.auth import require_auth
from server.src.data.dto.MetricsDTO import MetricsDTO
from server.src.services.composition import Projection
from server.src.services.composition.models import ProfileParams

projection_bp = Blueprint("projection", __name__, url_prefix="/api")


@projection_bp.get("/projection")
@require_auth
def projection():
    weeks = request.args.get("weeks", default=4, type=int)
    base = request.args.get("base", default="real")
    base_regression = "real_and_projected" if base == "real_projected" else "real_only"

    user_manager = current_app.extensions["user_manager"]
    log_manager = current_app.extensions["log_manager"]
    profile = user_manager.get_profile(g.user_id)
    real_logs = [
        log for log in log_manager.list_logs(g.user_id) if log.source == "real"
    ]
    engine_inputs = log_manager.to_engine_inputs(real_logs)

    profile_params = ProfileParams(
        height_cm=profile.height_cm,
        sex=profile.sex,
        birthdate=profile.birthdate,
        target_bf=profile.target_bf,
        weekly_rate=profile.weekly_rate,
    )
    try:
        results = Projection.project_series(
            profile_params, engine_inputs, weeks, base_regression
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify([asdict(MetricsDTO.from_domain(result)) for result in results])
