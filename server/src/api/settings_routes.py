"""Per-user engine-tunable routes: the Phase 1.5 energy-model constants
(TEF, kcal/kg fat, NEAT step factor) and Phase 1.3 alert thresholds,
historized like a goal plan (`GET /api/users/me/goals`). A user who has
never overridden anything gets `is_default: true` and today's fixed
`constants.py` values.
"""

from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, current_app, g, jsonify, request

from server.src.api.auth import require_auth
from server.src.data.dto.EngineSettingsDTO import EngineSettingsDTO
from server.src.services.EngineSettingsManager import (
    FIELDS,
    EngineSettingsManagerError,
)

settings_bp = Blueprint("settings", __name__, url_prefix="/api")


def _manager():
    return current_app.extensions["engine_settings_manager"]


@settings_bp.get("/users/me/settings")
@require_auth
def get_settings():
    active = _manager().get_active(g.user_id)
    return jsonify(asdict(EngineSettingsDTO.from_domain(active)))


@settings_bp.put("/users/me/settings")
@require_auth
def update_settings():
    payload = request.get_json(force=True) or {}
    overrides = {key: payload[key] for key in FIELDS if key in payload}
    try:
        updated = _manager().update_settings(g.user_id, **overrides)
    except EngineSettingsManagerError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(asdict(EngineSettingsDTO.from_domain(updated)))


@settings_bp.get("/users/me/settings/history")
@require_auth
def settings_history():
    history = _manager().list_history(g.user_id)
    return jsonify([asdict(EngineSettingsDTO.from_domain(s)) for s in history])
