from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from server.src.data.domain.AlertLog import AlertLog


@dataclass(frozen=True)
class AlertLogDTO:
    alert_id: int
    type: str
    severity: str
    date: str
    message: str
    value: float
    threshold: float
    acknowledged_at: Optional[str]

    @staticmethod
    def from_domain(alert_log: AlertLog) -> "AlertLogDTO":
        return AlertLogDTO(
            alert_id=alert_log.alert_id,
            type=alert_log.type,
            severity=alert_log.severity,
            date=alert_log.date.isoformat(),
            message=alert_log.message,
            value=alert_log.value,
            threshold=alert_log.threshold,
            acknowledged_at=(
                alert_log.acknowledged_at.isoformat()
                if alert_log.acknowledged_at
                else None
            ),
        )
