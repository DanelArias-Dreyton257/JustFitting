"""CRUD routes for weekly body logs."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from flask import Blueprint, current_app, g, jsonify, request

from server.src.api.auth import require_auth
from server.src.data.dto.BodyLogDTO import BodyLogDTO

log_bp = Blueprint("logs", __name__, url_prefix="/api")


def _log_manager():
    return current_app.extensions["log_manager"]


def _optional_float(value):
    """`None` (missing key or explicit JSON `null`) means "not logged", not
    `0.0` -- Phase 3.4's macro fields must stay unset, not zeroed."""
    return None if value is None else float(value)


@log_bp.get("/logs")
@require_auth
def list_logs():
    logs = _log_manager().list_logs(g.user_id)
    return jsonify([asdict(BodyLogDTO.from_domain(log)) for log in logs])


@log_bp.post("/logs")
@require_auth
def create_log():
    payload = request.get_json(force=True) or {}
    try:
        log = _log_manager().create_log(
            user_id=g.user_id,
            log_date=date.fromisoformat(payload["date"]),
            weight_kg=float(payload["weight_kg"]),
            waist_cm=float(payload["waist_cm"]),
            neck_cm=float(payload["neck_cm"]),
            intake_kcal=float(payload["intake_kcal"]),
            steps=float(payload["steps"]),
            intake_is_real=bool(payload.get("intake_is_real", True)),
            cardio_kcal=float(payload.get("cardio_kcal", 0.0)),
            source=payload.get("source", "real"),
            granularity=payload.get("granularity", "weekly"),
            carbs_g=_optional_float(payload.get("carbs_g")),
            fat_g=_optional_float(payload.get("fat_g")),
            protein_g=_optional_float(payload.get("protein_g")),
        )
    except (KeyError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(asdict(BodyLogDTO.from_domain(log))), 201


@log_bp.put("/logs/<int:log_id>")
@require_auth
def update_log(log_id: int):
    existing = _log_manager().get_log(log_id)
    if existing is None or existing.user_id != g.user_id:
        return jsonify({"error": "log not found"}), 404

    payload = request.get_json(force=True) or {}
    fields = {}
    for key in (
        "weight_kg",
        "waist_cm",
        "neck_cm",
        "intake_kcal",
        "steps",
        "intake_is_real",
        "cardio_kcal",
        "source",
        "granularity",
    ):
        if key in payload:
            fields[key] = payload[key]
    for key in ("carbs_g", "fat_g", "protein_g"):
        if key in payload:
            fields[key] = _optional_float(payload[key])
    if "date" in payload:
        fields["date"] = date.fromisoformat(payload["date"])

    try:
        log = _log_manager().update_log(log_id, **fields)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(asdict(BodyLogDTO.from_domain(log)))


@log_bp.delete("/logs/<int:log_id>")
@require_auth
def delete_log(log_id: int):
    existing = _log_manager().get_log(log_id)
    if existing is None or existing.user_id != g.user_id:
        return jsonify({"error": "log not found"}), 404
    _log_manager().delete_log(log_id)
    return "", 204
