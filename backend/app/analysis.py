from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

LONDON = ZoneInfo("Europe/London")


def calculate_decision_cutoff(delivery_date: date) -> datetime:
    """Return the illustrative noon UK cutoff on the day before delivery.

    Noon is a configurable business assumption for this analysis, not a
    confirmed official client purchasing deadline.
    """
    cutoff_date = delivery_date - timedelta(days=1)
    return datetime.combine(cutoff_date, time(12), tzinfo=LONDON)


def parse_timestamp(value: str | datetime | None) -> datetime | None:
    """Return a timestamp in UK time, or None when the value is missing."""
    if value is None or pd.isna(value):
        return None

    timestamp = pd.Timestamp(value).to_pydatetime()
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=LONDON)
    return timestamp.astimezone(LONDON)


def _records_to_frame(records: list[dict], columns: tuple[str, ...]) -> pd.DataFrame:
    """Create a DataFrame and add any columns required by the analysis."""
    frame = pd.DataFrame(records)
    for column in columns:
        if column not in frame:
            frame[column] = None
    if not frame.empty:
        frame["startTime"] = frame["startTime"].map(parse_timestamp)
    return frame


def _hourly_actuals(actual_frame: pd.DataFrame) -> pd.DataFrame:
    """Average half-hourly WIND readings so they match hourly forecasts."""
    if actual_frame.empty:
        return actual_frame

    actual_frame = actual_frame[actual_frame["startTime"].notna()].copy()
    actual_frame = actual_frame[actual_frame["fuelType"].eq("WIND")]
    actual_frame["generation"] = pd.to_numeric(
        actual_frame["generation"], errors="coerce"
    )
    actual_frame = actual_frame.dropna(subset=["generation"])
    actual_frame["startTime"] = actual_frame["startTime"].dt.floor("h")
    return (
        actual_frame.groupby("startTime", as_index=False)["generation"]
        .mean()
        .assign(fuelType="WIND")
    )


def _filter_delivery_date(
    frame: pd.DataFrame, delivery_date: date | None
) -> pd.DataFrame:
    """Keep only records whose delivery timestamp belongs to the requested day."""
    if frame.empty or delivery_date is None:
        return frame
    return frame[
        frame["startTime"].map(
            lambda timestamp: timestamp is not None
            and timestamp.date() == delivery_date
        )
    ]


def select_forecasts(
    forecasts: list[dict],
    actuals: list[dict],
    cutoff: datetime,
    delivery_date: date | None = None,
) -> tuple[list[dict], dict[str, dict[str, int] | list[float]]]:
    """Select cutoff-safe forecasts and match them with WIND actuals."""
    cutoff = parse_timestamp(cutoff)
    forecast_frame = _records_to_frame(
        forecasts, ("startTime", "publishTime", "generation")
    )
    actual_frame = _records_to_frame(
        actuals, ("startTime", "generation", "fuelType")
    )

    forecast_frame = _filter_delivery_date(forecast_frame, delivery_date)
    actual_frame = _filter_delivery_date(actual_frame, delivery_date)
    actual_frame = _hourly_actuals(actual_frame)

    if not forecast_frame.empty:
        forecast_frame = forecast_frame[forecast_frame["startTime"].notna()]
        forecast_frame["publishTime"] = forecast_frame["publishTime"].map(
            parse_timestamp
        )
        forecast_frame["generation"] = pd.to_numeric(
            forecast_frame["generation"], errors="coerce"
        )
        eligible = forecast_frame[
            forecast_frame["publishTime"].notna()
            & (forecast_frame["publishTime"] <= cutoff)
            & forecast_frame["generation"].notna()
        ].sort_values(["startTime", "publishTime"])
        selected_forecasts = eligible.drop_duplicates("startTime", keep="last")
    else:
        selected_forecasts = forecast_frame

    actual_by_time = {}
    if not actual_frame.empty:
        actual_by_time = actual_frame.set_index("startTime")["generation"].to_dict()

    results = []
    delivery_times = sorted(
        set(selected_forecasts["startTime"]) | set(actual_by_time)
    )
    for delivery_time in delivery_times:
        forecast_rows = selected_forecasts[
            selected_forecasts["startTime"].eq(delivery_time)
        ]
        has_forecast = not forecast_rows.empty
        forecast_value = (
            float(forecast_rows.iloc[0]["generation"]) if has_forecast else None
        )
        publish_time = (
            forecast_rows.iloc[0]["publishTime"].to_pydatetime()
            if has_forecast
            else None
        )
        actual_value = actual_by_time.get(delivery_time)
        error = (
            forecast_value - actual_value
            if forecast_value is not None and actual_value is not None
            else None
        )
        status = "matched"
        if forecast_value is None:
            status = "missing_forecast"
        elif actual_value is None:
            status = "missing_actual"

        results.append(
            {
                "delivery_time": delivery_time,
                "forecast_generation": forecast_value,
                "forecast_publish_time": publish_time,
                "actual_generation": (
                    float(actual_value) if actual_value is not None else None
                ),
                "error": error,
                "absolute_error": abs(error) if error is not None else None,
                "status": status,
            }
        )

    matched_errors = [
        result["error"] for result in results if result["error"] is not None
    ]
    counts = {
        "intervals": len(results),
        "matched": len(matched_errors),
        "missing_forecast": sum(
            result["status"] == "missing_forecast" for result in results
        ),
        "missing_actual": sum(
            result["status"] == "missing_actual" for result in results
        ),
        "excluded_after_cutoff": (
            int(
                (
                    forecast_frame["publishTime"].notna()
                    & (forecast_frame["publishTime"] > cutoff)
                ).sum()
            )
            if not forecast_frame.empty
            else 0
        ),
    }
    return results, {"counts": counts, "errors": matched_errors}


def calculate_metrics(results: list[dict]) -> dict[str, float | None]:
    """Calculate accuracy metrics using only matched forecast/actual pairs."""
    errors = [result["error"] for result in results if result["error"] is not None]
    if not errors:
        return {"mae": None, "rmse": None, "bias": None, "mape": None}

    absolute_errors = [abs(error) for error in errors]
    return {
        "mae": sum(absolute_errors) / len(errors),
        "rmse": (sum(error**2 for error in errors) / len(errors)) ** 0.5,
        "bias": sum(errors) / len(errors),
        "mape": None,
    }


def delivery_bounds(delivery_date: date) -> tuple[datetime, datetime]:
    """Return the start and end of a delivery date in UK time."""
    start = datetime.combine(delivery_date, time.min, tzinfo=LONDON)
    return start, start + pd.Timedelta(days=1).to_pytimedelta()
