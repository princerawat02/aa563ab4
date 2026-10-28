from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.analysis import calculate_decision_cutoff, calculate_metrics, select_forecasts

LONDON = ZoneInfo("Europe/London")
CUTOFF = datetime(2026, 1, 1, 12, tzinfo=LONDON)


def test_delivery_date_calculates_previous_day_noon_cutoff():
    assert calculate_decision_cutoff(date(2026, 1, 15)) == datetime(
        2026, 1, 14, 12, tzinfo=LONDON
    )
    assert calculate_decision_cutoff(date(2026, 1, 16)) == datetime(
        2026, 1, 15, 12, tzinfo=LONDON
    )


def test_latest_eligible_forecast_is_selected():
    forecasts = [
        {
            "startTime": "2026-01-02T13:00:00Z",
            "publishTime": "2026-01-01T10:00:00Z",
            "generation": 100,
        },
        {
            "startTime": "2026-01-02T13:00:00Z",
            "publishTime": "2026-01-01T11:00:00Z",
            "generation": 120,
        },
        {
            "startTime": "2026-01-02T13:00:00Z",
            "publishTime": "2026-01-01T13:00:00Z",
            "generation": 999,
        },
    ]
    actuals = [
        {
            "startTime": "2026-01-02T13:00:00Z",
            "generation": 100,
            "fuelType": "WIND",
        }
    ]

    results, details = select_forecasts(forecasts, actuals, CUTOFF)

    assert results[0]["forecast_generation"] == 120
    assert results[0]["actual_generation"] == 100
    assert results[0]["error"] == 20
    assert details["counts"]["excluded_after_cutoff"] == 1


def test_each_delivery_interval_gets_its_own_latest_eligible_forecast():
    forecasts = [
        {
            "startTime": "2026-01-02T13:00:00Z",
            "publishTime": "2026-01-01T10:00:00Z",
            "generation": 100,
        },
        {
            "startTime": "2026-01-02T13:00:00Z",
            "publishTime": "2026-01-01T11:00:00Z",
            "generation": 110,
        },
        {
            "startTime": "2026-01-02T14:00:00Z",
            "publishTime": "2026-01-01T09:00:00Z",
            "generation": 200,
        },
    ]
    actuals = [
        {"startTime": "2026-01-02T13:00:00Z", "generation": 100, "fuelType": "WIND"},
        {"startTime": "2026-01-02T13:30:00Z", "generation": 120, "fuelType": "WIND"},
        {"startTime": "2026-01-02T14:00:00Z", "generation": 180, "fuelType": "WIND"},
        {"startTime": "2026-01-02T14:30:00Z", "generation": 220, "fuelType": "WIND"},
    ]

    results, _ = select_forecasts(forecasts, actuals, CUTOFF, date(2026, 1, 2))

    assert [row["forecast_generation"] for row in results] == [110, 200]


def test_forecast_for_another_delivery_date_is_excluded():
    forecasts = [
        {
            "startTime": "2026-01-03T13:00:00Z",
            "publishTime": "2026-01-01T10:00:00Z",
            "generation": 999,
        }
    ]
    actuals = [
        {"startTime": "2026-01-02T13:00:00Z", "generation": 100, "fuelType": "WIND"},
        {"startTime": "2026-01-02T13:30:00Z", "generation": 100, "fuelType": "WIND"},
    ]

    results, _ = select_forecasts(forecasts, actuals, CUTOFF, date(2026, 1, 2))

    assert results[0]["forecast_generation"] is None
    assert results[0]["status"] == "missing_forecast"


def test_five_pm_forecast_is_excluded_by_noon_cutoff():
    forecasts = [
        {
            "startTime": "2026-01-15T13:00:00Z",
            "publishTime": "2026-01-14T17:00:00Z",
            "generation": 999,
        }
    ]
    actuals = [
        {"startTime": "2026-01-15T13:00:00Z", "generation": 100, "fuelType": "WIND"},
        {"startTime": "2026-01-15T13:30:00Z", "generation": 100, "fuelType": "WIND"},
    ]
    noon_cutoff = datetime(2026, 1, 14, 12, tzinfo=LONDON)

    results, details = select_forecasts(
        forecasts, actuals, noon_cutoff, date(2026, 1, 15)
    )

    assert results[0]["forecast_generation"] is None
    assert details["counts"]["excluded_after_cutoff"] == 1


def test_utc_and_london_cutoffs_represent_same_instant():
    forecasts = [
        {
            "startTime": "2026-01-02T13:00:00Z",
            "publishTime": "2026-01-01T12:00:00Z",
            "generation": 120,
        }
    ]
    actuals = [
        {"startTime": "2026-01-02T13:00:00Z", "generation": 100, "fuelType": "WIND"},
        {"startTime": "2026-01-02T13:30:00Z", "generation": 100, "fuelType": "WIND"},
    ]

    results, _ = select_forecasts(
        forecasts,
        actuals,
        datetime.fromisoformat("2026-01-01T12:00:00+00:00"),
        date(2026, 1, 2),
    )

    assert results[0]["status"] == "matched"


def test_forecast_published_at_cutoff_is_eligible():
    forecasts = [
        {
            "startTime": "2026-01-02T13:00:00Z",
            "publishTime": "2026-01-01T12:00:00Z",
            "generation": 120,
        }
    ]
    actuals = [
        {
            "startTime": "2026-01-02T13:00:00Z",
            "generation": 100,
            "fuelType": "WIND",
        }
    ]

    results, details = select_forecasts(forecasts, actuals, CUTOFF)

    assert results[0]["status"] == "matched"
    assert details["counts"]["excluded_after_cutoff"] == 0


def test_missing_forecast_is_not_replaced_with_zero():
    forecasts = []
    actuals = [
        {
            "startTime": "2026-01-02T13:00:00Z",
            "generation": 100,
            "fuelType": "WIND",
        }
    ]

    results, details = select_forecasts(forecasts, actuals, CUTOFF)

    assert results[0]["forecast_generation"] is None
    assert results[0]["error"] is None
    assert results[0]["status"] == "missing_forecast"
    assert details["counts"]["matched"] == 0


def test_missing_actual_is_not_replaced_with_zero():
    forecasts = [
        {
            "startTime": "2026-01-02T13:00:00Z",
            "publishTime": "2026-01-01T10:00:00Z",
            "generation": 120,
        }
    ]

    results, details = select_forecasts(forecasts, [], CUTOFF, date(2026, 1, 2))

    assert results[0]["actual_generation"] is None
    assert results[0]["error"] is None
    assert results[0]["status"] == "missing_actual"
    assert details["counts"]["matched"] == 0


def test_changing_cutoff_changes_selected_forecast():
    forecasts = [
        {
            "startTime": "2026-01-02T13:00:00Z",
            "publishTime": "2026-01-01T10:00:00Z",
            "generation": 100,
        },
        {
            "startTime": "2026-01-02T13:00:00Z",
            "publishTime": "2026-01-01T11:00:00Z",
            "generation": 120,
        },
    ]
    actuals = [
        {"startTime": "2026-01-02T13:00:00Z", "generation": 100, "fuelType": "WIND"},
        {"startTime": "2026-01-02T13:30:00Z", "generation": 100, "fuelType": "WIND"},
    ]

    early_results, _ = select_forecasts(
        forecasts,
        actuals,
        datetime(2026, 1, 1, 10, 30, tzinfo=LONDON),
        date(2026, 1, 2),
    )
    late_results, _ = select_forecasts(forecasts, actuals, CUTOFF, date(2026, 1, 2))

    assert early_results[0]["forecast_generation"] == 100
    assert late_results[0]["forecast_generation"] == 120


def test_non_wind_actuals_are_ignored():
    actuals = [
        {
            "startTime": "2026-01-02T13:00:00Z",
            "generation": 900,
            "fuelType": "CCGT",
        }
    ]

    results, _ = select_forecasts([], actuals, CUTOFF)

    assert results == []


def test_half_hourly_actuals_are_averaged_to_hourly():
    forecasts = [
        {
            "startTime": "2026-01-02T13:00:00Z",
            "publishTime": "2026-01-01T10:00:00Z",
            "generation": 120,
        }
    ]
    actuals = [
        {
            "startTime": "2026-01-02T13:00:00Z",
            "generation": 100,
            "fuelType": "WIND",
        },
        {
            "startTime": "2026-01-02T13:30:00Z",
            "generation": 110,
            "fuelType": "WIND",
        },
    ]

    results, details = select_forecasts(forecasts, actuals, CUTOFF)

    assert results[0]["actual_generation"] == 105
    assert results[0]["error"] == 15
    assert details["counts"]["matched"] == 1


def test_metrics_use_only_matched_errors():
    results = [
        {"error": 10, "actual_generation": 100},
        {"error": -20, "actual_generation": 200},
        {"error": None, "actual_generation": None},
    ]

    metrics = calculate_metrics(results)

    assert metrics["mae"] == 15
    assert metrics["rmse"] == 250**0.5
    assert metrics["bias"] == -5
