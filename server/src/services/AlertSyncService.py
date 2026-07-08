"""Detects alerts over a user's current series and persists them, so a
`GET /api/alerts` (or the report endpoint) reflects a stable, dismissable
alert list instead of a fresh, id-less recomputation on every read.
Shared by `alerts_routes.py` and `user_routes.py`'s report endpoint.
"""

from __future__ import annotations

from typing import List

from flask import Flask

from server.src.data.domain.AlertLog import AlertLog
from server.src.services.composition import Alerts, EnergyReconciliation, GainQuality, MacroTargets
from server.src.services.MetricsSeriesService import compute_series_for_user


def sync_alerts(
    app: Flask, user_id: int, include_acknowledged: bool = False
) -> List[AlertLog]:
    logs, results = compute_series_for_user(app, user_id)
    engine_settings_manager = app.extensions["engine_settings_manager"]
    thresholds = engine_settings_manager.to_engine_constants(
        engine_settings_manager.get_active(user_id)
    )
    goal_plan_manager = app.extensions["goal_plan_manager"]
    goal = goal_plan_manager.get_active(user_id)
    goal_history_count = len(goal_plan_manager.list_history(user_id))
    gain_quality = GainQuality.compute_gain_quality(results) if results else []
    reconciliation = (
        EnergyReconciliation.compute_energy_reconciliation(logs, results, thresholds)
        if results
        else []
    )
    macro_targets = (
        MacroTargets.compute_macro_targets(logs, results, thresholds) if results else []
    )
    detected = Alerts.detect_alerts(
        results,
        thresholds,
        goal,
        gain_quality=gain_quality,
        reconciliation=reconciliation,
        logs=logs,
        macro_targets=macro_targets,
        goal_history_count=goal_history_count,
    )
    alert_log_dao = app.extensions["alert_log_dao"]
    alert_log_dao.record_detected(user_id, detected)
    return alert_log_dao.list_for_user(user_id, include_acknowledged=include_acknowledged)
