"""Plan-adjustment preview: recompute target calories and weeks-to-goal for
a candidate target_bf/weekly_rate against the latest real log, without
persisting a new goal plan. Committing the change still goes through the
existing `PUT /api/users/me`, which historizes it via `GoalPlanManager`.
"""

from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, current_app, g, jsonify, request

from server.src.api.auth import require_auth
from server.src.data.dto.MetricsDTO import MetricsDTO
from server.src.services.composition import CompositionEngine
from server.src.services.composition.models import ProfileParams

plan_bp = Blueprint("plan", __name__, url_prefix="/api/plan")


@plan_bp.get("/preview")
@require_auth
def preview():
    user_manager = current_app.extensions["user_manager"]
    log_manager = current_app.extensions["log_manager"]
    goal_plan_manager = current_app.extensions["goal_plan_manager"]

    profile = user_manager.get_profile(g.user_id)
    goal = goal_plan_manager.get_active(g.user_id)
    if profile is None or goal is None:
        return jsonify({"error": "no active goal plan"}), 404

    real_logs = [log for log in log_manager.list_logs(g.user_id) if log.source == "real"]
    if not real_logs:
        return jsonify({"error": "no logs yet"}), 404

    try:
        target_bf = float(request.args.get("target_bf", goal.target_bf))
        weekly_rate = float(request.args.get("weekly_rate", goal.weekly_rate))
    except (TypeError, ValueError):
        return jsonify({"error": "target_bf and weekly_rate must be numbers"}), 400

    candidate_profile = ProfileParams(
        height_cm=profile.height_cm,
        sex=profile.sex,
        birthdate=profile.birthdate,
        target_bf=target_bf,
        weekly_rate=weekly_rate,
    )

    engine_inputs = log_manager.to_engine_inputs(real_logs)
    prev_weight_kg = engine_inputs[-2].weight_kg if len(engine_inputs) > 1 else None

    try:
        result = CompositionEngine.compute_row(
            candidate_profile, engine_inputs[-1], prev_weight_kg
        )
    except (ValueError, ZeroDivisionError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(asdict(MetricsDTO.from_domain(result)))
