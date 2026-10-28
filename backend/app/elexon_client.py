from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .config import ELEXON_BASE_URL, REQUEST_TIMEOUT_SECONDS

LONDON = ZoneInfo("Europe/London")


class ElexonClientError(RuntimeError):
    pass


class ElexonClient:
    """Fetch the actual and forecast datasets used by the dashboard."""

    def __init__(self, base_url: str = ELEXON_BASE_URL):
        self.base_url = base_url.rstrip("/")

    async def _fetch(
        self, dataset: str, params: dict[str, str]
    ) -> list[dict[str, Any]]:
        """Fetch and validate records from an Elexon stream."""
        url = f"{self.base_url}/datasets/{dataset}/stream"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=10)
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ElexonClientError(
                f"Unable to retrieve {dataset} from Elexon"
            ) from exc
        records = payload.get("data", payload) if isinstance(payload, dict) else payload
        if not isinstance(records, list) or any(
            not isinstance(row, dict) for row in records
        ):
            raise ElexonClientError(f"Elexon returned an invalid {dataset} response")
        return records

    async def get_day(
        self,
        dataset: str,
        start: datetime,
        end: datetime,
        cutoff: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch records whose delivery interval belongs to the requested day."""
        if dataset == "WINDFOR":
            if cutoff is None:
                raise ValueError("A cutoff is required when fetching WINDFOR")
            cutoff = cutoff.astimezone(LONDON)
            # Request a broad historical window, then apply the exact cutoff
            # and delivery-date filters in analysis.
            publication_start = min(
                start - timedelta(days=30), cutoff - timedelta(days=30)
            )
            params = {
                "publishDateTimeFrom": publication_start.astimezone(ZoneInfo("UTC"))
                .isoformat()
                .replace("+00:00", "Z"),
                "publishDateTimeTo": end.astimezone(ZoneInfo("UTC"))
                .isoformat()
                .replace("+00:00", "Z"),
            }
        else:
            params = {
                "settlementDateFrom": start.date().isoformat(),
                "settlementDateTo": end.date().isoformat(),
            }
        records = await self._fetch(
            dataset,
            params,
        )
        # BMRS date ranges are inclusive, so filter by delivery date after fetching.
        return [
            record
            for record in records
            if isinstance(record.get("startTime"), str)
            and self._is_delivery_date(record["startTime"], start)
        ]

    @staticmethod
    def _is_delivery_date(value: str, start: datetime) -> bool:
        """Compare delivery dates after converting Elexon timestamps to UK time."""
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=LONDON)
        return timestamp.astimezone(LONDON).date() == start.date()

    async def get_wind_data(
        self, start: datetime, end: datetime, cutoff: datetime
    ) -> tuple[list[dict], list[dict]]:
        """Fetch actuals and forecasts concurrently."""
        actuals, forecasts = await self._fetch_pair(start, end, cutoff)
        return actuals, forecasts

    async def _fetch_pair(
        self, start: datetime, end: datetime, cutoff: datetime
    ) -> tuple[list[dict], list[dict]]:
        import asyncio

        return await asyncio.gather(
            self.get_day("FUELHH", start, end),
            self.get_day("WINDFOR", start, end, cutoff),
        )
