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
from server.src.services.GoalPlanManager import GoalPlanManagerError, check_goal_coherence
from server.src.services.LogResampler import is_computable, resample_to_weekly

plan_bp = Blueprint("plan", __name__, url_prefix="/api/plan")


@plan_bp.get("/preview")
@require_auth
def preview():
    user_manager = current_app.extensions["user_manager"]
    log_manager = current_app.extensions["log_manager"]
    goal_plan_manager = current_app.extensions["goal_plan_manager"]
    engine_settings_manager = current_app.extensions["engine_settings_manager"]

    profile = user_manager.get_profile(g.user_id)
    goal = goal_plan_manager.get_active(g.user_id)
    if profile is None or goal is None:
        return jsonify({"error": "no active goal plan"}), 404

    real_logs = [log for log in log_manager.list_logs(g.user_id) if log.source == "real"]
    if not real_logs:
        return jsonify({"error": "no logs yet"}), 404

    # Same resample-then-filter pipeline MetricsSeriesService.
    # compute_series_for_user uses, rather than the raw last log by date --
    # a mixed daily/weekly account (README's Phase 7.3-7.5 Health Connect
    # sync) can have its most recent raw row be a still-partial one (e.g. a
    # weekly body-comp entry with no steps/intake of its own yet, completed
    # by daily-synced rows in the same ISO week only once resampled), which
    # would otherwise reach compute_row directly and 400 with "cannot
    # compute a row missing required fields" despite the account's data for
    # that week genuinely being complete once combined.
    computable_logs = [log for log in resample_to_weekly(real_logs) if is_computable(log)]
    if not computable_logs:
        return jsonify({"error": "no computable logs yet"}), 404

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

    engine_inputs = log_manager.to_engine_inputs(computable_logs)
    prev_weight_kg = engine_inputs[-2].weight_kg if len(engine_inputs) > 1 else None
    engine_constants = engine_settings_manager.to_engine_constants(
        engine_settings_manager.get_active(g.user_id)
    )

    try:
        result = CompositionEngine.compute_row(
            candidate_profile, engine_inputs[-1], prev_weight_kg, engine_constants
        )
    except (ValueError, ZeroDivisionError) as exc:
        return jsonify({"error": str(exc)}), 400

    # Phase 8.2: body_fat never depends on target_bf/weekly_rate (see the
    # README's Composition Model section), so `result.body_fat` is the
    # account's real current body fat regardless of the candidate params
    # just computed against it -- reusable here without a second engine
    # call, and checked before commit rather than only after a coincidental
    # domain error deep in compute_row.
    try:
        check_goal_coherence(result.body_fat, target_bf, weekly_rate)
    except GoalPlanManagerError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(asdict(MetricsDTO.from_domain(result)))
