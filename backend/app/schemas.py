from datetime import datetime

from pydantic import BaseModel


class IntervalResult(BaseModel):
    delivery_time: datetime
    forecast_generation: float | None = None
    forecast_publish_time: datetime | None = None
    actual_generation: float | None = None
    error: float | None = None
    absolute_error: float | None = None
    status: str


class AnalysisResponse(BaseModel):
    delivery_date: str
    decision_cutoff: datetime
    intervals: list[IntervalResult]
    metrics: dict[str, float | None]
    counts: dict[str, int]
    data_quality: dict[str, object]
    retrieved_at: datetime
    source: str
    demo_mode: bool
