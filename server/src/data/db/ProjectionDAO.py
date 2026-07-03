from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Sequence, Tuple

from server.src.data.db.DB import DB
from server.src.data.domain.Projection import Projection
from server.src.services.composition.models import LogInput


class ProjectionDAO:
    def __init__(self, db: DB):
        self.db = db

    def create_many(
        self,
        *,
        user_id: int,
        run_id: str,
        rows: Sequence[LogInput],
        source_model: str,
        base_regression: str,
        generated_at: datetime,
        activity_model: str = "constant",
        trend_model: str = "ols",
    ) -> List[Projection]:
        created: List[Projection] = []
        generated_at_iso = generated_at.isoformat()
        for row in rows:
            cursor = self.db.execute(
                """
                INSERT INTO projections
                    (user_id, run_id, projected_date, estimated_weight,
                     estimated_waist, estimated_neck, source_model,
                     base_regression, generated_at, activity_model, trend_model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    run_id,
                    row.date.isoformat(),
                    row.weight_kg,
                    row.waist_cm,
                    row.neck_cm,
                    source_model,
                    base_regression,
                    generated_at_iso,
                    activity_model,
                    trend_model,
                ),
            )
            created.append(self.get_by_id(cursor.lastrowid))
        return created

    def get_by_id(self, projection_id: int) -> Optional[Projection]:
        row = self.db.query_one(
            "SELECT * FROM projections WHERE projection_id = ?", (projection_id,)
        )
        return Projection.from_row(row) if row else None

    def list_runs(self, user_id: int) -> List[dict]:
        rows = self.db.query(
            """
            SELECT run_id, MIN(generated_at) AS generated_at,
                   base_regression, COUNT(*) AS weeks
            FROM projections
            WHERE user_id = ?
            GROUP BY run_id
            ORDER BY generated_at DESC
            """,
            (user_id,),
        )
        return [dict(row) for row in rows]

    def get_run(self, user_id: int, run_id: str) -> List[Projection]:
        rows = self.db.query(
            """
            SELECT * FROM projections
            WHERE user_id = ? AND run_id = ?
            ORDER BY projected_date ASC
            """,
            (user_id, run_id),
        )
        return [Projection.from_row(row) for row in rows]

    def get_latest_run(self, user_id: int) -> Optional[Tuple[str, List[Projection]]]:
        row = self.db.query_one(
            """
            SELECT run_id FROM projections
            WHERE user_id = ?
            ORDER BY generated_at DESC
            LIMIT 1
            """,
            (user_id,),
        )
        if row is None:
            return None
        run_id = row["run_id"]
        return run_id, self.get_run(user_id, run_id)
