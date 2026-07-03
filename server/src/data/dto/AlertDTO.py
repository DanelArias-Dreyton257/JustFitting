from __future__ import annotations

from dataclasses import dataclass

from server.src.services.composition.Alerts import Alert


@dataclass(frozen=True)
class AlertDTO:
    type: str
    severity: str
    date: str
    message: str
    value: float
    threshold: float

    @staticmethod
    def from_domain(alert: Alert) -> "AlertDTO":
        return AlertDTO(
            type=alert.type,
            severity=alert.severity,
            date=alert.date.isoformat(),
            message=alert.message,
            value=alert.value,
            threshold=alert.threshold,
        )
