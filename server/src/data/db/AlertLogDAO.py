from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Sequence

from server.src.data.db.DB import DB
from server.src.data.domain.AlertLog import AlertLog
from server.src.services.composition.Alerts import Alert


class AlertLogDAO:
    def __init__(self, db: DB):
        self.db = db

    def record_detected(self, user_id: int, alerts: Sequence[Alert]) -> None:
        detected_at = datetime.now(timezone.utc).isoformat()
        for alert in alerts:
            self.db.execute(
                """
                INSERT OR IGNORE INTO alert_log
                    (user_id, type, severity, date, message, value, threshold, detected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    alert.type,
                    alert.severity,
                    alert.date.isoformat(),
                    alert.message,
                    alert.value,
                    alert.threshold,
                    detected_at,
                ),
            )

    def list_for_user(
        self, user_id: int, include_acknowledged: bool = True
    ) -> List[AlertLog]:
        if include_acknowledged:
            rows = self.db.query(
                """
                SELECT * FROM alert_log
                WHERE user_id = ?
                ORDER BY date DESC, alert_id DESC
                """,
                (user_id,),
            )
        else:
            rows = self.db.query(
                """
                SELECT * FROM alert_log
                WHERE user_id = ? AND acknowledged_at IS NULL
                ORDER BY date DESC, alert_id DESC
                """,
                (user_id,),
            )
        return [AlertLog.from_row(row) for row in rows]

    def acknowledge(self, user_id: int, alert_id: int) -> Optional[AlertLog]:
        existing = self.db.query_one(
            "SELECT * FROM alert_log WHERE alert_id = ? AND user_id = ?",
            (alert_id, user_id),
        )
        if existing is None:
            return None
        self.db.execute(
            "UPDATE alert_log SET acknowledged_at = ? WHERE alert_id = ?",
            (datetime.now(timezone.utc).isoformat(), alert_id),
        )
        return self.get_by_id(alert_id)

    def get_by_id(self, alert_id: int) -> Optional[AlertLog]:
        row = self.db.query_one("SELECT * FROM alert_log WHERE alert_id = ?", (alert_id,))
        return AlertLog.from_row(row) if row else None
