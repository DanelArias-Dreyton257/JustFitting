"""Derived-metrics routes: latest snapshot and chart-ready time series."""

from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, current_app, g, jsonify, request

from server.src.api.auth import require_auth
from server.src.data.dto.MetricsDTO import MetricsDTO
from server.src.services.composition.CompositionEngine import compute_series
from server.src.services.composition.models import ProfileParams

metrics_bp = Blueprint("metrics", __name__, url_prefix="/api/metrics")


def _profile_params(profile) -> ProfileParams:
    return ProfileParams(
        height_cm=profile.height_cm,
        sex=profile.sex,
        birthdate=profile.birthdate,
        target_bf=profile.target_bf,
        weekly_rate=profile.weekly_rate,
    )


def _compute_results(user_id: int):
    user_manager = current_app.extensions["user_manager"]
    log_manager = current_app.extensions["log_manager"]
    profile = user_manager.get_profile(user_id)
    logs = log_manager.list_logs(user_id)
    engine_inputs = log_manager.to_engine_inputs(logs)
    if not engine_inputs:
        return [], []
    results = compute_series(_profile_params(profile), engine_inputs)
    return logs, results


@metrics_bp.get("/latest")
@require_auth
def latest():
    logs, results = _compute_results(g.user_id)
    real_pairs = [
        (log, result) for log, result in zip(logs, results) if log.source == "real"
    ]
    if not real_pairs:
        return jsonify({"error": "no logs yet"}), 404
    _, latest_result = real_pairs[-1]
    return jsonify(asdict(MetricsDTO.from_domain(latest_result)))


@metrics_bp.get("/series")
@require_auth
def series():
    metric = request.args.get("metric")
    _, results = _compute_results(g.user_id)
    payload = [asdict(MetricsDTO.from_domain(result)) for result in results]
    if metric:
        payload = [{"date": row["date"], metric: row.get(metric)} for row in payload]
    return jsonify(payload)
