"""Derived-metrics routes: latest snapshot and chart-ready time series."""

from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, current_app, g, jsonify, request

from server.src.api.auth import require_auth
from server.src.data.dto.MetricsDTO import MetricsDTO
from server.src.services.composition import CompositionEngine
from server.src.services.MetricsSeriesService import compute_series_for_user

metrics_bp = Blueprint("metrics", __name__, url_prefix="/api/metrics")


def _compute_results(user_id: int):
    return compute_series_for_user(current_app, user_id)


@metrics_bp.get("/latest")
@require_auth
def latest():
    logs, results = _compute_results(g.user_id)
    real_pairs = [
        (log, result) for log, result in zip(logs, results) if log.source == "real"
    ]
    if not real_pairs:
        return jsonify({"error": "no logs yet"}), 404
    latest_log, latest_result = real_pairs[-1]
    dto = MetricsDTO.from_domain(
        latest_result,
        log_id=latest_log.log_id,
        engine_version=CompositionEngine.ENGINE_VERSION,
    )
    return jsonify(asdict(dto))


@metrics_bp.get("/series")
@require_auth
def series():
    metric = request.args.get("metric")
    logs, results = _compute_results(g.user_id)
    payload = [
        asdict(
            MetricsDTO.from_domain(
                result, log_id=log.log_id, engine_version=CompositionEngine.ENGINE_VERSION
            )
        )
        for log, result in zip(logs, results)
    ]
    if metric:
        payload = [{"date": row["date"], metric: row.get(metric)} for row in payload]
    return jsonify(payload)
