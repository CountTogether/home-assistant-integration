"""DataUpdateCoordinator for CountTogether."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CountTogetherClient, CountTogetherApiError
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class CountTogetherCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches all counters and keeps them up-to-date.

    Data shape: {counter_id: counter_dict, ...}
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: CountTogetherClient,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self._ws_task: asyncio.Task | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch counters from API."""
        try:
            counters = await self.client.list_counters()
            return {c["id"]: c for c in counters}
        except CountTogetherApiError as err:
            raise UpdateFailed(f"Error fetching CountTogether data: {err}") from err

    async def async_start_websocket(self) -> None:
        """Start the WebSocket listener for real-time updates."""
        if self._ws_task and not self._ws_task.done():
            return
        self._ws_task = asyncio.create_task(self._ws_listener())

    async def async_stop_websocket(self) -> None:
        """Stop the WebSocket listener."""
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None

    async def _ws_listener(self) -> None:
        """Connect to WebSocket and process messages; reconnect on error."""
        reconnect_delay = 5.0
        while True:
            try:
                session = aiohttp.ClientSession()
                try:
                    async with session.ws_connect(
                        self.client.ws_url,
                        headers={"Authorization": f"Bearer {self.client.token}"},
                    ) as ws:
                        _LOGGER.debug("CountTogether WebSocket connected")
                        reconnect_delay = 5.0
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await self._handle_ws_message(msg.data)
                            elif msg.type in (
                                aiohttp.WSMsgType.ERROR,
                                aiohttp.WSMsgType.CLOSED,
                            ):
                                break
                finally:
                    await session.close()
            except asyncio.CancelledError:
                return
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "CountTogether WebSocket disconnected: %s - reconnecting in %ss",
                    err,
                    reconnect_delay,
                )
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 120)

    async def _handle_ws_message(self, raw: str) -> None:
        """Process a JSON-RPC 2.0 WebSocket message."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        method = data.get("method")
        params = data.get("params", {})
        counter_id = params.get("counterId")

        if method == "counterUpdated" and counter_id:
            if self.data and counter_id in self.data:
                # Merge updated fields into local data and trigger listeners
                updated = {**self.data[counter_id]}
                for key in ("name", "type", "value"):
                    if key in params:
                        updated[key] = params[key]
                self.async_set_updated_data({**self.data, counter_id: updated})
            else:
                # Unknown counter – could be newly shared/created; reload all
                _LOGGER.debug(
                    "Received counterUpdated for unknown counter %s – refreshing",
                    counter_id,
                )
                await self.async_refresh()

        elif method == "counterDeleted" and counter_id:
            if self.data and counter_id in self.data:
                # Remove counter from local data
                new_data = {k: v for k, v in self.data.items() if k != counter_id}
                self.async_set_updated_data(new_data)
                # Remove the associated device from the device registry
                await self._async_remove_device(counter_id)

        elif method == "counterMemberlistChanged":
            await self.async_refresh()

    async def _async_remove_device(self, counter_id: str) -> None:
        """Remove the HA device associated with a deleted counter."""
        dev_reg = dr.async_get(self.hass)
        device = dev_reg.async_get_device(identifiers={(DOMAIN, counter_id)})
        if device:
            _LOGGER.debug("Removing device for deleted counter %s", counter_id)
            dev_reg.async_remove_device(device.id)
