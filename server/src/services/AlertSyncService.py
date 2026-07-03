"""Detects alerts over a user's current series and persists them, so a
`GET /api/alerts` (or the report endpoint) reflects a stable, dismissable
alert list instead of a fresh, id-less recomputation on every read.
Shared by `alerts_routes.py` and `user_routes.py`'s report endpoint.
"""

from __future__ import annotations

from typing import List

from flask import Flask

from server.src.data.domain.AlertLog import AlertLog
from server.src.services.composition import Alerts
from server.src.services.MetricsSeriesService import compute_series_for_user


def sync_alerts(
    app: Flask, user_id: int, include_acknowledged: bool = False
) -> List[AlertLog]:
    _, results = compute_series_for_user(app, user_id)
    detected = Alerts.detect_alerts(results)
    alert_log_dao = app.extensions["alert_log_dao"]
    alert_log_dao.record_detected(user_id, detected)
    return alert_log_dao.list_for_user(user_id, include_acknowledged=include_acknowledged)
