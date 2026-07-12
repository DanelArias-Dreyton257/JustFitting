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
        log_date = date.fromisoformat(payload["date"])
    except (KeyError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    # `body_logs` has a UNIQUE(user_id, date) constraint -- without this
    # guard, a date that already has a row (e.g. a Health Connect-synced
    # day) raises an unhandled sqlite3.IntegrityError here, a 500 instead
    # of a clean error. Same guard the import route (user_routes.py) already
    # uses for the same reason. The client's own log wizard no longer hits
    # this at all (it upserts by date instead, see app.js), but this stays
    # as defense-in-depth for any other caller of this "strictly create a
    # new row" route.
    if _log_manager().get_by_date(g.user_id, log_date) is not None:
        return jsonify({"error": "a log already exists for this date"}), 400
    try:
        log = _log_manager().create_log(
            user_id=g.user_id,
            log_date=log_date,
            # Phase 7.4 (partial logs, see README): optional, not
            # required -- `_optional_float` treats a missing key the same
            # as an explicit `null`, "not logged yet by any source".
            weight_kg=_optional_float(payload.get("weight_kg")),
            intake_kcal=_optional_float(payload.get("intake_kcal")),
            steps=_optional_float(payload.get("steps")),
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


# Phase 7.4 (partial logs & independent-source merging, see README): unlike
# POST /logs (a brand-new row) or PUT /logs/<id> (edit a row you already
# know the id of), this upserts by date -- merging in only the given
# fields, creating a new partial row if none exists yet for that date.
# This is the order-/source-independent primitive Phase 7.5's per-source
# "Sync now" calls; every field is optional, and any field not present in
# the payload is left completely untouched (never reset to null).
_UPSERT_FLOAT_FIELDS = (
    "weight_kg",
    "intake_kcal",
    "steps",
    "cardio_kcal",
    "carbs_g",
    "fat_g",
    "protein_g",
)


@log_bp.get("/logs/by-date/<log_date>")
@require_auth
def get_log_by_date(log_date: str):
    """Phase 10.2 (Today dashboard section, see README): the read-side
    counterpart of the upsert route below, both wrapping
    `LogManager.get_by_date` -- lets the client ask "what does today's
    (possibly still-partial) row look like" without listing every log."""
    try:
        parsed_date = date.fromisoformat(log_date)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    log = _log_manager().get_by_date(g.user_id, parsed_date)
    if log is None:
        return jsonify({"error": "no log for that date"}), 404
    return jsonify(asdict(BodyLogDTO.from_domain(log)))


@log_bp.put("/logs/by-date/<log_date>")
@require_auth
def upsert_log_by_date(log_date: str):
    payload = request.get_json(force=True) or {}
    try:
        parsed_date = date.fromisoformat(log_date)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    fields = {}
    for key in _UPSERT_FLOAT_FIELDS:
        if key in payload:
            fields[key] = _optional_float(payload[key])
    for key in ("intake_is_real", "source"):
        if key in payload:
            fields[key] = payload[key]

    default_granularity = payload.get("granularity", "weekly")
    try:
        log = _log_manager().upsert_fields(
            g.user_id, parsed_date, fields, default_granularity=default_granularity
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(asdict(BodyLogDTO.from_domain(log)))


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
