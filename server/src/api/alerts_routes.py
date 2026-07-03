"""Alerts & feedback: surfaces the composition engine's guardrails
(implausible week-over-week change, plateau/stagnation, excessive lean-mass
loss, and goal-trajectory deviation) as structured, user-facing alerts.
"""

from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, current_app, g, jsonify

from server.src.api.auth import require_auth
from server.src.data.dto.AlertDTO import AlertDTO
from server.src.services.composition import Alerts
from server.src.services.MetricsSeriesService import compute_series_for_user

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api")


@alerts_bp.get("/alerts")
@require_auth
def list_alerts():
    _, results = compute_series_for_user(current_app, g.user_id)
    alerts = Alerts.detect_alerts(results)
    return jsonify([asdict(AlertDTO.from_domain(alert)) for alert in alerts])
