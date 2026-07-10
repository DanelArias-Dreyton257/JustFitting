"""Daily activity goal (steps/cardio) routes -- Phase 10.2, see README.
Independent of the main body-fat goal (`/api/users/me/goals`): unset by
default, no coherence check, historized the same way.
"""

from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, current_app, g, jsonify, request

from server.src.api.auth import require_auth
from server.src.data.dto.ActivityGoalDTO import ActivityGoalDTO
from server.src.services.ActivityGoalManager import ActivityGoalManagerError

activity_goal_bp = Blueprint("activity_goal", __name__, url_prefix="/api/users/me")


def _manager():
    return current_app.extensions["activity_goal_manager"]


@activity_goal_bp.get("/activity-goal")
@require_auth
def get_activity_goal():
    active = _manager().get_active(g.user_id)
    return jsonify(asdict(ActivityGoalDTO.from_domain(active)))


@activity_goal_bp.put("/activity-goal")
@require_auth
def update_activity_goal():
    payload = request.get_json(force=True) or {}
    steps_goal = payload.get("steps_goal")
    cardio_kcal_goal = payload.get("cardio_kcal_goal")
    try:
        updated = _manager().set_goal(
            g.user_id,
            steps_goal=float(steps_goal) if steps_goal is not None else None,
            cardio_kcal_goal=float(cardio_kcal_goal) if cardio_kcal_goal is not None else None,
        )
    except ActivityGoalManagerError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(asdict(ActivityGoalDTO.from_domain(updated)))


@activity_goal_bp.get("/activity-goal/history")
@require_auth
def activity_goal_history():
    history = _manager().list_history(g.user_id)
    return jsonify([asdict(ActivityGoalDTO.from_domain(goal)) for goal in history])
