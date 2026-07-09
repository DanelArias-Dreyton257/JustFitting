"""Forecast routes: extrapolate future weekly rows from real logs, and
optionally persist a run so it can be inspected later without recomputing.
"""

from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, current_app, g, jsonify, request

from server.src.api.auth import require_auth
from server.src.data.dto.MetricsDTO import MetricsDTO
from server.src.data.dto.ProjectionDTO import ProjectionDTO
from server.src.services.composition import Projection
from server.src.services.LogResampler import is_computable, resample_to_weekly

projection_bp = Blueprint("projection", __name__, url_prefix="/api")


def _base_regression(base: str) -> str:
    return "real_and_projected" if base == "real_projected" else "real_only"


def _activity_model(activity: str) -> str:
    return "trend" if activity == "trend" else "constant"


def _trend_model(trend: str) -> str:
    return "weighted_ols" if trend == "weighted_ols" else "ols"


def _forecast_inputs(user_id: int):
    user_manager = current_app.extensions["user_manager"]
    log_manager = current_app.extensions["log_manager"]
    goal_plan_manager = current_app.extensions["goal_plan_manager"]
    engine_settings_manager = current_app.extensions["engine_settings_manager"]

    profile = user_manager.get_profile(user_id)
    goal = goal_plan_manager.get_active(user_id)
    profile_params = goal_plan_manager.build_profile_params(profile, goal)
    real_logs = [log for log in log_manager.list_logs(user_id) if log.source == "real"]
    # Phase 5.3: same active-goal-period scoping as
    # MetricsSeriesService.compute_series_for_user, so a forecast's trend
    # regression isn't fit over data from before the account's last goal
    # change.
    period_start = goal_plan_manager.active_period_start(user_id)
    if period_start is not None:
        real_logs = [log for log in real_logs if log.date >= period_start]
    # Same resample-then-filter pipeline MetricsSeriesService.
    # compute_series_for_user/plan_routes.preview use -- a mixed
    # daily/weekly account (README's Phase 7.3-7.5 Health Connect sync) can
    # have its most recent raw row be a still-partial one, completed only
    # once daily-synced rows in the same ISO week are resampled in; feeding
    # the engine raw, unresampled rows risks a spurious "cannot compute a
    # row missing required fields" here too.
    computable_logs = [log for log in resample_to_weekly(real_logs) if is_computable(log)]
    engine_inputs = log_manager.to_engine_inputs(computable_logs)
    engine_constants = engine_settings_manager.to_engine_constants(
        engine_settings_manager.get_active(user_id)
    )
    return profile_params, engine_inputs, engine_constants


@projection_bp.get("/projection")
@require_auth
def projection():
    weeks = request.args.get("weeks", default=4, type=int)
    base_regression = _base_regression(request.args.get("base", default="real"))
    activity_model = _activity_model(request.args.get("activity", default="constant"))
    trend_model = _trend_model(request.args.get("trend_model", default="ols"))

    profile_params, engine_inputs, engine_constants = _forecast_inputs(g.user_id)
    try:
        pairs = Projection.project_series_with_inputs(
            profile_params,
            engine_inputs,
            weeks,
            base_regression,
            activity_model,
            engine_constants,
            trend_model,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    payload = []
    for log_input, result in pairs:
        row = asdict(MetricsDTO.from_domain(result))
        row["estimated_weight"] = log_input.weight_kg
        row["estimated_waist"] = log_input.waist_cm
        row["estimated_neck"] = log_input.neck_cm
        payload.append(row)
    return jsonify(payload)


@projection_bp.post("/projection")
@require_auth
def save_projection():
    payload = request.get_json(silent=True) or {}
    weeks = int(payload.get("weeks", request.args.get("weeks", 4)))
    base_regression = _base_regression(
        payload.get("base", request.args.get("base", "real"))
    )
    activity_model = _activity_model(
        payload.get("activity", request.args.get("activity", "constant"))
    )
    trend_model = _trend_model(
        payload.get("trend_model", request.args.get("trend_model", "ols"))
    )

    projection_service = current_app.extensions["projection_service"]
    profile_params, engine_inputs, engine_constants = _forecast_inputs(g.user_id)
    try:
        run_id, rows = projection_service.save_run(
            g.user_id,
            profile_params,
            engine_inputs,
            weeks,
            base_regression,
            activity_model,
            engine_constants,
            trend_model,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return (
        jsonify(
            {
                "run_id": run_id,
                "rows": [asdict(ProjectionDTO.from_domain(row)) for row in rows],
            }
        ),
        201,
    )


@projection_bp.get("/projections")
@require_auth
def list_projection_runs():
    projection_service = current_app.extensions["projection_service"]
    return jsonify(projection_service.list_runs(g.user_id))


@projection_bp.get("/projections/<run_id>")
@require_auth
def get_projection_run(run_id: str):
    projection_service = current_app.extensions["projection_service"]
    rows = projection_service.get_run(g.user_id, run_id)
    if not rows:
        return jsonify({"error": "projection run not found"}), 404
    return jsonify([asdict(ProjectionDTO.from_domain(row)) for row in rows])
