from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional

from server.src.data.db.DB import DB
from server.src.data.domain.BodyLog import BodyLog


class BodyLogDAO:
    def __init__(self, db: DB):
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        date: date,
        weight_kg: float,
        waist_cm: float,
        neck_cm: float,
        intake_kcal: float,
        intake_is_real: bool,
        steps: float,
        cardio_kcal: float = 0.0,
        source: str = "real",
        granularity: str = "weekly",
        carbs_g: Optional[float] = None,
        fat_g: Optional[float] = None,
        protein_g: Optional[float] = None,
    ) -> BodyLog:
        created_at = datetime.now(timezone.utc).isoformat()
        cursor = self.db.execute(
            """
            INSERT INTO body_logs
                (user_id, date, weight_kg, waist_cm, neck_cm, intake_kcal,
                 intake_is_real, steps, cardio_kcal, source, created_at, granularity,
                 carbs_g, fat_g, protein_g)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                date.isoformat(),
                weight_kg,
                waist_cm,
                neck_cm,
                intake_kcal,
                int(intake_is_real),
                steps,
                cardio_kcal,
                source,
                created_at,
                granularity,
                carbs_g,
                fat_g,
                protein_g,
            ),
        )
        return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, log_id: int) -> Optional[BodyLog]:
        row = self.db.query_one("SELECT * FROM body_logs WHERE log_id = ?", (log_id,))
        return BodyLog.from_row(row) if row else None

    def list_for_user(self, user_id: int) -> List[BodyLog]:
        rows = self.db.query(
            "SELECT * FROM body_logs WHERE user_id = ? ORDER BY date ASC", (user_id,)
        )
        return [BodyLog.from_row(row) for row in rows]

    def get_by_user_and_date(self, user_id: int, log_date: date) -> Optional[BodyLog]:
        row = self.db.query_one(
            "SELECT * FROM body_logs WHERE user_id = ? AND date = ?",
            (user_id, log_date.isoformat()),
        )
        return BodyLog.from_row(row) if row else None

    def update(self, log_id: int, **fields) -> Optional[BodyLog]:
        if not fields:
            return self.get_by_id(log_id)
        columns = [f"{key} = ?" for key in fields]
        params = []
        for key, value in fields.items():
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            elif key == "intake_is_real":
                value = int(value)
            params.append(value)
        params.append(log_id)
        self.db.execute(
            f"UPDATE body_logs SET {', '.join(columns)} WHERE log_id = ?", tuple(params)
        )
        return self.get_by_id(log_id)

    def delete(self, log_id: int) -> None:
        self.db.execute("DELETE FROM body_logs WHERE log_id = ?", (log_id,))

    def delete_all_for_user(self, user_id: int) -> None:
        self.db.execute("DELETE FROM body_logs WHERE user_id = ?", (user_id,))
