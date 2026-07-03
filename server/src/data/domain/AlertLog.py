"""A persisted alert: an `Alerts.Alert` detection anchored to a stable id,
so it can be looked back at and acknowledged instead of only existing for
the duration of one `GET /api/alerts` call.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime
from typing import Optional


@dataclass
class AlertLog:
    alert_id: int
    user_id: int
    type: str
    severity: str
    date: date_type
    message: str
    value: float
    threshold: float
    detected_at: datetime
    acknowledged_at: Optional[datetime]

    @staticmethod
    def from_row(row) -> "AlertLog":
        return AlertLog(
            alert_id=row["alert_id"],
            user_id=row["user_id"],
            type=row["type"],
            severity=row["severity"],
            date=date_type.fromisoformat(row["date"]),
            message=row["message"],
            value=row["value"],
            threshold=row["threshold"],
            detected_at=datetime.fromisoformat(row["detected_at"]),
            acknowledged_at=(
                datetime.fromisoformat(row["acknowledged_at"])
                if row["acknowledged_at"]
                else None
            ),
        )
