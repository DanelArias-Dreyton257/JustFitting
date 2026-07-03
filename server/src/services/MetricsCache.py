"""Caches `CompositionEngine` results per log so historical values stay
reproducible across `ENGINE_VERSION` bumps, instead of recomputing on every
read. A cache hit only happens when every log in the series already has a
snapshot at the current engine version; any log create/update/delete or
goal-plan change invalidates the whole user's cache (see `LogManager` and
`GoalPlanManager`), so the next read recomputes and repopulates it.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from server.src.data.db.MetricsSnapshotDAO import MetricsSnapshotDAO
from server.src.data.domain.BodyLog import BodyLog
from server.src.services.composition import CompositionEngine
from server.src.services.composition.models import (
    CompositionResult,
    EngineConstants,
    LogInput,
    ProfileParams,
)


class MetricsCache:
    def __init__(self, snapshot_dao: MetricsSnapshotDAO):
        self.snapshot_dao = snapshot_dao

    def get_or_compute_series(
        self,
        profile: ProfileParams,
        logs: Sequence[BodyLog],
        engine_inputs: Sequence[LogInput],
        engine_constants: Optional[EngineConstants] = None,
    ) -> List[CompositionResult]:
        ordered_logs = sorted(logs, key=lambda log: log.date)
        log_ids = [log.log_id for log in ordered_logs]
        if not log_ids:
            return []

        cached = self.snapshot_dao.get_many(log_ids, CompositionEngine.ENGINE_VERSION)
        if len(cached) == len(log_ids):
            return [cached[log_id] for log_id in log_ids]

        results = CompositionEngine.compute_series(profile, engine_inputs, engine_constants)
        for log, result in zip(ordered_logs, results):
            self.snapshot_dao.upsert(log.log_id, CompositionEngine.ENGINE_VERSION, result)
        return results

    def invalidate_for_user(self, user_id: int) -> None:
        self.snapshot_dao.delete_for_user(user_id)
