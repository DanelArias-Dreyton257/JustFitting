"""CRUD routes for sporadic body measurements (Phase 9.1/9.2, see README) --
deliberately separate from /api/logs, matching the "separate logging tab"
the feature is built around.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from flask import Blueprint, current_app, g, jsonify, request

from server.src.api.auth import require_auth
from server.src.data.dto.BodyMeasurementDTO import BodyMeasurementDTO
from server.src.services.BodyMeasurementManager import (
    MEASUREMENT_FIELDS,
    BodyMeasurementManagerError,
)

body_measurement_bp = Blueprint(
    "body_measurements", __name__, url_prefix="/api/body-measurements"
)


def _manager():
    return current_app.extensions["body_measurement_manager"]


def _optional_float(value):
    return None if value is None else float(value)


def _fields_from_payload(payload: dict) -> dict:
    return {
        key: _optional_float(payload[key]) for key in MEASUREMENT_FIELDS if key in payload
    }


@body_measurement_bp.get("")
@require_auth
def list_measurements():
    measurements = _manager().list_for_user(g.user_id)
    return jsonify([asdict(BodyMeasurementDTO.from_domain(m)) for m in measurements])


@body_measurement_bp.post("")
@require_auth
def upsert_measurement():
    """Upserts by date rather than always inserting -- the Body view's
    date-picker-plus-save-button flow can re-save the same day (e.g.
    correcting a typo) without tripping `UNIQUE(user_id, date)`."""
    payload = request.get_json(force=True) or {}
    try:
        measurement_date = date.fromisoformat(payload["date"])
    except (KeyError, ValueError) as exc:
        return jsonify({"error": f"invalid date: {exc}"}), 400
    fields = _fields_from_payload(payload)
    try:
        measurement = _manager().upsert_for_date(g.user_id, measurement_date, fields)
    except BodyMeasurementManagerError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(asdict(BodyMeasurementDTO.from_domain(measurement))), 201


@body_measurement_bp.put("/<int:measurement_id>")
@require_auth
def update_measurement(measurement_id: int):
    existing = _manager().get_by_id(measurement_id)
    if existing is None or existing.user_id != g.user_id:
        return jsonify({"error": "measurement not found"}), 404

    payload = request.get_json(force=True) or {}
    fields = _fields_from_payload(payload)
    try:
        measurement = _manager().update(measurement_id, **fields)
    except BodyMeasurementManagerError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(asdict(BodyMeasurementDTO.from_domain(measurement)))


@body_measurement_bp.delete("/<int:measurement_id>")
@require_auth
def delete_measurement(measurement_id: int):
    existing = _manager().get_by_id(measurement_id)
    if existing is None or existing.user_id != g.user_id:
        return jsonify({"error": "measurement not found"}), 404
    _manager().delete(measurement_id)
    return "", 204
