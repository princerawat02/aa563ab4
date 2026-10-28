import asyncio
from datetime import datetime

from app.elexon_client import ElexonClient


def test_windfor_request_covers_cutoff_and_delivery_day():
    client = ElexonClient()
    captured = {}

    async def fake_fetch(dataset, params):
        captured["dataset"] = dataset
        captured["params"] = params
        return [
            {
                "startTime": "2026-01-15T13:00:00Z",
                "publishTime": "2026-01-14T11:00:00Z",
                "generation": 120,
            }
        ]

    client._fetch = fake_fetch
    start = datetime.fromisoformat("2026-01-15T00:00:00+00:00")
    end = datetime.fromisoformat("2026-01-16T00:00:00+00:00")
    cutoff = datetime.fromisoformat("2026-01-14T12:00:00+00:00")

    records = asyncio.run(client.get_day("WINDFOR", start, end, cutoff))

    assert records
    assert captured["dataset"] == "WINDFOR"
    assert captured["params"]["publishDateTimeFrom"] == "2025-12-15T12:00:00Z"
    assert captured["params"]["publishDateTimeTo"] == "2026-01-16T00:00:00Z"


def test_delivery_date_filter_uses_timezone_aware_timestamp():
    client = ElexonClient()
    start = datetime.fromisoformat("2026-01-15T00:00:00+00:00")

    assert client._is_delivery_date("2026-01-15T00:30:00Z", start)
    assert not client._is_delivery_date("2026-01-16T00:00:00Z", start)
