from __future__ import annotations

from dataclasses import dataclass

from server.src.data.domain.Projection import Projection


@dataclass(frozen=True)
class ProjectionDTO:
    projection_id: int
    user_id: int
    run_id: str
    projected_date: str
    estimated_weight: float
    estimated_waist: float
    estimated_neck: float
    source_model: str
    base_regression: str
    generated_at: str
    activity_model: str

    @staticmethod
    def from_domain(projection: Projection) -> "ProjectionDTO":
        return ProjectionDTO(
            projection_id=projection.projection_id,
            user_id=projection.user_id,
            run_id=projection.run_id,
            projected_date=projection.projected_date.isoformat(),
            estimated_weight=projection.estimated_weight,
            estimated_waist=projection.estimated_waist,
            estimated_neck=projection.estimated_neck,
            source_model=projection.source_model,
            base_regression=projection.base_regression,
            generated_at=projection.generated_at.isoformat(),
            activity_model=projection.activity_model,
        )
