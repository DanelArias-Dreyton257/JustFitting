"""Alerts & feedback: surfaces the composition engine's guardrails
(implausible week-over-week change, plateau/stagnation, excessive lean-mass
loss, and goal-trajectory deviation) as structured, user-facing alerts.

Detections are persisted (`alert_log` table, deduped on `(user_id, type,
date)`) so an alert can be acknowledged/dismissed and stays gone across
reads, instead of being recomputed fresh -- and forgotten -- every time.
"""

from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, current_app, g, jsonify, request

from server.src.api.auth import require_auth
from server.src.data.dto.AlertLogDTO import AlertLogDTO
from server.src.services.AlertSyncService import sync_alerts

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api")


@alerts_bp.get("/alerts")
@require_auth
def list_alerts():
    include_acknowledged = request.args.get("include_acknowledged", "false").lower() == "true"
    alerts = sync_alerts(current_app, g.user_id, include_acknowledged=include_acknowledged)
    return jsonify([asdict(AlertLogDTO.from_domain(alert)) for alert in alerts])


@alerts_bp.post("/alerts/<int:alert_id>/acknowledge")
@require_auth
def acknowledge_alert(alert_id: int):
    dao = current_app.extensions["alert_log_dao"]
    updated = dao.acknowledge(g.user_id, alert_id)
    if updated is None:
        return jsonify({"error": "alert not found"}), 404
    return jsonify(asdict(AlertLogDTO.from_domain(updated)))
