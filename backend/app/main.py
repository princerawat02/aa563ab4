from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .analysis import (
    calculate_metrics,
    calculate_decision_cutoff,
    delivery_bounds,
    select_forecasts,
)
from .cache import DataCache
from .config import FRONTEND_ORIGIN, USE_DEMO_DATA
from .elexon_client import ElexonClient, ElexonClientError
from .schemas import AnalysisResponse

app = FastAPI(title="Wind Generation Forecast API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in FRONTEND_ORIGIN.split(",")],
    allow_methods=["GET"],
    allow_headers=["*"],
)

client = ElexonClient()
cache = DataCache()
LONDON = ZoneInfo("Europe/London")
SOURCE = "Elexon BMRS FUELHH and WINDFOR"


def validate_delivery_date(delivery_date: date) -> None:
    """Allow only the January 2026 historical period used by this dashboard."""
    if delivery_date.year != 2026 or delivery_date.month != 1:
        raise HTTPException(
            status_code=422,
            detail="Only delivery dates in January 2026 are supported.",
        )


def demo_data(delivery_date: date) -> tuple[list[dict], list[dict]]:
    """Create clearly-labelled synthetic data for local development."""
    start = datetime.combine(delivery_date, time.min, tzinfo=LONDON)
    actuals = []
    forecasts = []

    for interval in range(48):
        delivery_time = start + timedelta(minutes=30 * interval)
        actual = 4000 + ((interval * 173) % 1200)
        actuals.append(
            {
                "startTime": delivery_time.isoformat(),
                "generation": actual,
                "fuelType": "WIND",
            }
        )
        if interval % 2 == 0:
            forecasts.append(
                {
                    "startTime": delivery_time.isoformat(),
                    "publishTime": (delivery_date - timedelta(days=1)).isoformat()
                    + "T10:00:00+00:00",
                    "generation": actual + (interval % 5 - 2) * 70,
                }
            )
    return actuals, forecasts


async def load_data(
    delivery_date: date, cutoff: datetime
) -> tuple[list[dict], list[dict]]:
    """Load one delivery day, using the small in-memory cache when available."""
    cache_key = f"{delivery_date.isoformat()}:{cutoff.isoformat()}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    if USE_DEMO_DATA:
        data = demo_data(delivery_date)
    else:
        data = await client.get_wind_data(*delivery_bounds(delivery_date), cutoff)

    cache.set(cache_key, data)
    return data


@app.get("/api/health")
async def health() -> dict[str, object]:
    """Report that the API is running."""
    return {"status": "ok", "service": "wind-forecast-api", "demo_mode": USE_DEMO_DATA}


@app.get("/api/analysis", response_model=AnalysisResponse)
async def analysis(
    delivery_date: date = Query(...),
) -> AnalysisResponse:
    """Return cutoff-safe forecast results and accuracy metrics for one day."""
    validate_delivery_date(delivery_date)
    cutoff = calculate_decision_cutoff(delivery_date)

    try:
        actuals, forecasts = await load_data(delivery_date, cutoff)
        intervals, details = select_forecasts(forecasts, actuals, cutoff, delivery_date)
    except ElexonClientError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    counts = details["counts"]
    return AnalysisResponse(
        delivery_date=delivery_date.isoformat(),
        decision_cutoff=cutoff,
        intervals=intervals,
        metrics=calculate_metrics(intervals),
        counts=counts,
        data_quality={
            "valid_matched_records": counts["matched"],
            "excluded_records": counts["intervals"] - counts["matched"],
            "duplicate_policy": (
                "Latest eligible forecast by publishTime; "
                "first valid duplicate actual."
            ),
        },
        retrieved_at=datetime.now(LONDON),
        source=SOURCE,
        demo_mode=USE_DEMO_DATA,
    )
