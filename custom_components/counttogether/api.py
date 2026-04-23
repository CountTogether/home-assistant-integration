"""CountTogether API client."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import BASE_URL, API_V2

_LOGGER = logging.getLogger(__name__)


class CountTogetherApiError(Exception):
    """Generic API error."""


class CountTogetherAuthError(CountTogetherApiError):
    """Authentication error."""


class CountTogetherNotFoundError(CountTogetherApiError):
    """Resource not found."""


class CountTogetherClient:
    """Async HTTP client for the CountTogether v2 API."""

    def __init__(
        self,
        api_token: str,
        session: aiohttp.ClientSession,
        timezone: str = "UTC",
        base_url: str = BASE_URL,
    ) -> None:
        self._token = api_token
        self._session = session
        self._timezone = timezone
        self._base = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self._base}{API_V2}{path}"
        if params is None:
            params = {}
        params.setdefault("timezone", self._timezone)

        async with self._session.request(
            method, url, headers=self._headers(), json=json, params=params
        ) as resp:
            if resp.status in (401, 403):
                raise CountTogetherAuthError(f"Authentication failed: {resp.status}")
            if resp.status == 404:
                raise CountTogetherNotFoundError(f"Not found: {path}")
            if not resp.ok:
                text = await resp.text()
                raise CountTogetherApiError(f"API error {resp.status}: {text}")
            if resp.status == 204:
                return None
            return await resp.json()

    async def list_counters(self) -> list[dict[str, Any]]:
        """Return list of all counters."""
        data = await self._request("GET", "/counters")
        if isinstance(data, list):
            return data
        return data.get("data", [])

    async def get_counter(self, counter_id: str) -> dict[str, Any]:
        """Return a single counter by ID."""
        data = await self._request("GET", f"/counters/{counter_id}")
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data

    async def increment(self, counter_id: str, amount: int = 1) -> int:
        """Increment an UpDown counter. Returns new value."""
        result = await self._request(
            "POST", f"/counters/{counter_id}/increment/{amount}"
        )
        return int(result)

    async def decrement(self, counter_id: str, amount: int = 1) -> int:
        """Decrement an UpDown counter. Returns new value."""
        result = await self._request(
            "POST", f"/counters/{counter_id}/decrement/{amount}"
        )
        return int(result)

    async def patch_counter(
        self,
        counter_id: str,
        *,
        name: str | None = None,
        value: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Patch a counter. Returns updated counter object."""
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if value is not None:
            payload["value"] = value
        if start_date is not None:
            payload["startDate"] = start_date
        if end_date is not None:
            payload["endDate"] = end_date
        data = await self._request("PATCH", f"/counters/{counter_id}", json=payload)
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data

    @property
    def ws_url(self) -> str:
        """WebSocket URL for real-time updates."""
        base = self._base
        if base.startswith("https://"):
            ws = "wss://" + base[len("https://"):]
        elif base.startswith("http://"):
            ws = "ws://" + base[len("http://"):]
        else:
            ws = base
        return f"{ws}{API_V2}/ws?timezone={self._timezone}"

    @property
    def token(self) -> str:
        return self._token

