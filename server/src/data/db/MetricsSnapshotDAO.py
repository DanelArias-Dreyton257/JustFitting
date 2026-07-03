"""Persists one `CompositionResult` per (log_id, engine_version).

Keyed this way so historical results stay reproducible if the engine's
formulas or compute order ever change (`CompositionEngine.ENGINE_VERSION`
bump) -- old snapshots are left untouched, only rows missing a snapshot at
the current version get (re)computed.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import date as date_cls
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from server.src.data.db.DB import DB
from server.src.services.composition.models import CompositionResult

_RESULT_FIELDS = [f.name for f in fields(CompositionResult)]


def _serialize(value):
    return value.isoformat() if isinstance(value, date_cls) else value


def _deserialize(name: str, value):
    if name == "date":
        return date_cls.fromisoformat(value)
    if name == "age":
        return int(value)
    return value


class MetricsSnapshotDAO:
    def __init__(self, db: DB):
        self.db = db

    def upsert(self, log_id: int, engine_version: int, result: CompositionResult) -> None:
        computed_at = datetime.now(timezone.utc).isoformat()
        columns = ["log_id", "engine_version", "computed_at", *_RESULT_FIELDS]
        values = [log_id, engine_version, computed_at] + [
            _serialize(getattr(result, name)) for name in _RESULT_FIELDS
        ]
        placeholders = ", ".join("?" for _ in columns)
        update_clause = ", ".join(
            f"{column} = excluded.{column}"
            for column in columns
            if column not in ("log_id", "engine_version")
        )
        self.db.execute(
            f"""
            INSERT INTO metrics_snapshots ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(log_id, engine_version) DO UPDATE SET {update_clause}
            """,
            tuple(values),
        )

    def get(self, log_id: int, engine_version: int) -> Optional[CompositionResult]:
        row = self.db.query_one(
            "SELECT * FROM metrics_snapshots WHERE log_id = ? AND engine_version = ?",
            (log_id, engine_version),
        )
        return self._to_result(row) if row else None

    def get_many(
        self, log_ids: Sequence[int], engine_version: int
    ) -> Dict[int, CompositionResult]:
        if not log_ids:
            return {}
        placeholders = ", ".join("?" for _ in log_ids)
        rows = self.db.query(
            f"""
            SELECT * FROM metrics_snapshots
            WHERE engine_version = ? AND log_id IN ({placeholders})
            """,
            (engine_version, *log_ids),
        )
        return {row["log_id"]: self._to_result(row) for row in rows}

    def delete_for_user(self, user_id: int) -> None:
        self.db.execute(
            """
            DELETE FROM metrics_snapshots
            WHERE log_id IN (SELECT log_id FROM body_logs WHERE user_id = ?)
            """,
            (user_id,),
        )

    @staticmethod
    def _to_result(row) -> CompositionResult:
        kwargs = {name: _deserialize(name, row[name]) for name in _RESULT_FIELDS}
        return CompositionResult(**kwargs)
