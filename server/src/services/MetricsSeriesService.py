"""Computes a user's chronological composition-metrics series, reusing the
per-log snapshot cache. Shared by `/api/metrics` and `/api/alerts` routes so
both operate over the exact same series.
"""

from __future__ import annotations

from typing import List, Tuple

from flask import Flask

from server.src.data.domain.BodyLog import BodyLog
from server.src.services.composition.models import CompositionResult
from server.src.services.LogResampler import resample_to_weekly


def compute_series_for_user(
    app: Flask, user_id: int
) -> Tuple[List[BodyLog], List[CompositionResult]]:
    user_manager = app.extensions["user_manager"]
    log_manager = app.extensions["log_manager"]
    goal_plan_manager = app.extensions["goal_plan_manager"]
    engine_settings_manager = app.extensions["engine_settings_manager"]
    metrics_cache = app.extensions["metrics_cache"]

    profile = user_manager.get_profile(user_id)
    logs = log_manager.list_logs(user_id)
    if not logs or profile is None:
        return [], []

    ordered_logs = sorted(logs, key=lambda log: log.date)
    # F6 (Phase 3.3): collapse any daily-granularity rows into one
    # representative row per ISO week before they reach the (inherently
    # weekly-cadence) engine; weekly-tagged rows pass through unchanged.
    resampled_logs = resample_to_weekly(ordered_logs)
    engine_inputs = log_manager.to_engine_inputs(resampled_logs)
    goal = goal_plan_manager.get_active(user_id)
    profile_params = goal_plan_manager.build_profile_params(profile, goal)
    engine_constants = engine_settings_manager.to_engine_constants(
        engine_settings_manager.get_active(user_id)
    )
    results = metrics_cache.get_or_compute_series(
        profile_params, resampled_logs, engine_inputs, engine_constants
    )
    return resampled_logs, results
