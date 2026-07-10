"""Persists forecast runs so a saved projection can be inspected later
without recomputing (see `docs/product_capabilities_spec.md` §15, `Projection`).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Sequence, Tuple

from server.src.data.db.ProjectionDAO import ProjectionDAO
from server.src.data.domain.Projection import Projection as ProjectionRow
from server.src.services.composition import Projection
from server.src.services.composition.Projection import MeasurementPoint
from server.src.services.composition.models import EngineConstants, LogInput, ProfileParams

SOURCE_MODEL = "ols_linear"


class ProjectionService:
    def __init__(self, projection_dao: ProjectionDAO):
        self.projection_dao = projection_dao

    def save_run(
        self,
        user_id: int,
        profile: ProfileParams,
        real_logs: Sequence[LogInput],
        weeks: int,
        base_regression: str = "real_only",
        activity_model: str = "constant",
        engine_constants: Optional[EngineConstants] = None,
        trend_model: str = "ols",
        measurement_history: Optional[Sequence[MeasurementPoint]] = None,
    ) -> Tuple[str, List[ProjectionRow]]:
        pairs = Projection.project_series_with_inputs(
            profile,
            real_logs,
            weeks,
            base_regression,
            activity_model,
            engine_constants,
            trend_model,
            measurement_history,
        )
        run_id = uuid.uuid4().hex
        generated_at = datetime.now(timezone.utc)
        rows = self.projection_dao.create_many(
            user_id=user_id,
            run_id=run_id,
            rows=[log for log, _ in pairs],
            source_model=SOURCE_MODEL,
            base_regression=base_regression,
            generated_at=generated_at,
            activity_model=activity_model,
            trend_model=trend_model,
        )
        return run_id, rows

    def list_runs(self, user_id: int) -> List[dict]:
        return self.projection_dao.list_runs(user_id)

    def get_run(self, user_id: int, run_id: str) -> List[ProjectionRow]:
        return self.projection_dao.get_run(user_id, run_id)

    def get_latest_run(
        self, user_id: int
    ) -> Optional[Tuple[str, List[ProjectionRow]]]:
        return self.projection_dao.get_latest_run(user_id)
