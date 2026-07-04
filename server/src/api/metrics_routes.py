"""Derived-metrics routes: latest snapshot and chart-ready time series."""

from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, current_app, g, jsonify, request

from server.src.api.auth import require_auth
from server.src.data.dto.AdherenceDTO import AdherenceDTO
from server.src.data.dto.EnergyReconciliationDTO import EnergyReconciliationDTO
from server.src.data.dto.GainQualityDTO import GainQualityDTO
from server.src.data.dto.IncrementAnalyticsDTO import IncrementAnalyticsDTO
from server.src.data.dto.MetricsDTO import MetricsDTO
from server.src.data.dto.TefDTO import TefDTO
from server.src.services.composition import (
    CompositionEngine,
    EnergyReconciliation,
    GainQuality,
    IncrementAnalytics,
    Tef,
)
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


@metrics_bp.get("/adherence")
@require_auth
def adherence():
    logs, results = _compute_results(g.user_id)
    if not logs:
        return jsonify({"error": "no logs yet"}), 404
    log_manager = current_app.extensions["log_manager"]
    mean_intake_diff_kcal = log_manager.compute_adherence(logs, results)
    real_log_count = sum(1 for log in logs if log.intake_is_real)
    dto = AdherenceDTO.from_values(mean_intake_diff_kcal, real_log_count)
    return jsonify(asdict(dto))


@metrics_bp.get("/gain-quality")
@require_auth
def gain_quality():
    _, results = _compute_results(g.user_id)
    if not results:
        return jsonify({"error": "no logs yet"}), 404
    engine_settings_manager = current_app.extensions["engine_settings_manager"]
    ec = engine_settings_manager.to_engine_constants(
        engine_settings_manager.get_active(g.user_id)
    )
    rows = GainQuality.compute_gain_quality(results)
    return jsonify(
        [asdict(GainQualityDTO.from_domain(row, ec.fat_ratio_ideal)) for row in rows]
    )


@metrics_bp.get("/energy-balance")
@require_auth
def energy_balance():
    logs, results = _compute_results(g.user_id)
    if not results:
        return jsonify({"error": "no logs yet"}), 404
    engine_settings_manager = current_app.extensions["engine_settings_manager"]
    ec = engine_settings_manager.to_engine_constants(
        engine_settings_manager.get_active(g.user_id)
    )
    rows = EnergyReconciliation.compute_energy_reconciliation(logs, results, ec)
    return jsonify(
        [
            asdict(EnergyReconciliationDTO.from_domain(row, ec.reconciliation_error_threshold_kcal))
            for row in rows
        ]
    )


@metrics_bp.get("/tef")
@require_auth
def tef():
    logs, results = _compute_results(g.user_id)
    if not results:
        return jsonify({"error": "no logs yet"}), 404
    engine_settings_manager = current_app.extensions["engine_settings_manager"]
    ec = engine_settings_manager.to_engine_constants(
        engine_settings_manager.get_active(g.user_id)
    )
    rows = Tef.compute_tef_breakdown(logs, results, ec)
    return jsonify([asdict(TefDTO.from_domain(row)) for row in rows])


@metrics_bp.get("/increment-analytics")
@require_auth
def increment_analytics():
    _, results = _compute_results(g.user_id)
    if not results:
        return jsonify({"error": "no logs yet"}), 404
    goal = current_app.extensions["goal_plan_manager"].get_active(g.user_id)
    if goal is None:
        return jsonify({"error": "no goal plan yet"}), 404
    rows = IncrementAnalytics.compute_increment_analytics(results, goal.weekly_rate)
    return jsonify(
        [asdict(IncrementAnalyticsDTO.from_domain(row, goal.weekly_rate)) for row in rows]
    )
