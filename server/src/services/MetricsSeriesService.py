"""Computes a user's chronological composition-metrics series, reusing the
per-log snapshot cache. Shared by `/api/metrics` and `/api/alerts` routes so
both operate over the exact same series.
"""

from __future__ import annotations

from typing import List, Tuple

from flask import Flask

from server.src.data.domain.BodyLog import BodyLog
from server.src.services.composition.models import CompositionResult
from server.src.services.LogResampler import is_computable, resample_to_weekly


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
    # Phase 5.3: once an account has actually changed its goal, only the
    # active goal's own period feeds the derived series -- otherwise a
    # goal change silently recomputes every historical week's
    # target/trajectory/deficit as if the new goal had applied the whole
    # time. See GoalPlanManager.active_period_start's docstring for why
    # this is skipped entirely for an account that's never changed its
    # goal, rather than a blanket `date >= goal.start_date` filter.
    period_start = goal_plan_manager.active_period_start(user_id)
    # The last real weigh-in before the active period, if any -- used only
    # as trajectory context (below), never re-included in the output, so
    # the first displayed row of a new goal period still has a genuine
    # predecessor instead of being treated as the start of history.
    context_prev_weight_kg = None
    if period_start is not None:
        preceding = [log for log in ordered_logs if log.date < period_start]
        if preceding:
            context_prev_weight_kg = preceding[-1].weight_kg
        ordered_logs = [log for log in ordered_logs if log.date >= period_start]
    if not ordered_logs:
        return [], []

    # F6 (Phase 3.3): collapse any daily-granularity rows into one
    # representative row per ISO week before they reach the (inherently
    # weekly-cadence) engine; weekly-tagged rows pass through unchanged.
    resampled_logs = resample_to_weekly(ordered_logs)
    # Phase 7.4 (partial logs, see README): a resampled week can still be
    # missing weight/waist/neck/intake/steps if no source (sync, manual
    # entry, import) has supplied one of them for any day in it -- exclude
    # it from the computed series the same way an unlogged week already
    # is, rather than let it reach the engine at all. The raw rows still
    # show up via GET /api/logs/export/the Log view regardless.
    computable_logs = [log for log in resampled_logs if is_computable(log)]
    engine_inputs = log_manager.to_engine_inputs(computable_logs)
    goal = goal_plan_manager.get_active(user_id)
    profile_params = goal_plan_manager.build_profile_params(profile, goal)
    engine_constants = engine_settings_manager.to_engine_constants(
        engine_settings_manager.get_active(user_id)
    )
    results = metrics_cache.get_or_compute_series(
        profile_params,
        computable_logs,
        engine_inputs,
        engine_constants,
        context_prev_weight_kg,
    )
    return computable_logs, results
