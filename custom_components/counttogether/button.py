"""Button entities for CountTogether."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import CountTogetherApiError
from .const import DOMAIN, COUNTER_TYPE_UPDOWN
from .coordinator import CountTogetherCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CountTogether button entities."""
    coordinator: CountTogetherCoordinator = hass.data[DOMAIN][entry.entry_id]

    known_ids: set[str] = set()

    @callback
    def _add_new_entities() -> None:
        if coordinator.data is None:
            return
        new_entities: list[ButtonEntity] = []
        for counter_id, counter in coordinator.data.items():
            if counter_id in known_ids:
                continue
            known_ids.add(counter_id)
            counter_type = counter.get("type", COUNTER_TYPE_UPDOWN)

            # Increment/Decrement buttons only for UpDown counters
            if counter_type == COUNTER_TYPE_UPDOWN:
                new_entities.append(IncrementButton(coordinator, counter_id))
                new_entities.append(DecrementButton(coordinator, counter_id))

        if new_entities:
            async_add_entities(new_entities)

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class _CounterBaseButton(CoordinatorEntity[CountTogetherCoordinator], ButtonEntity):
    """Base class for CountTogether button entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CountTogetherCoordinator, counter_id: str) -> None:
        self._counter_id = counter_id
        super().__init__(coordinator)

    @property
    def _counter(self) -> dict[str, Any] | None:
        if self.coordinator.data:
            return self.coordinator.data.get(self._counter_id)
        return None

    @property
    def device_info(self) -> DeviceInfo:
        counter = self._counter or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self._counter_id)},
            name=counter.get("name", self._counter_id),
            manufacturer="CountTogether",
            model=counter.get("type", "Counter"),
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._counter is not None


class IncrementButton(_CounterBaseButton):
    """Button to increment an UpDown counter by 1."""

    _attr_icon = "mdi:plus-circle-outline"

    @property
    def unique_id(self) -> str:
        return f"{self._counter_id}_increment"

    @property
    def name(self) -> str:
        return "Increment"

    async def async_press(self) -> None:
        """Increment the counter by 1."""
        try:
            await self.coordinator.client.increment(self._counter_id, 1)
            await self.coordinator.async_request_refresh()
        except CountTogetherApiError as err:
            _LOGGER.error("Failed to increment counter %s: %s", self._counter_id, err)


class DecrementButton(_CounterBaseButton):
    """Button to decrement an UpDown counter by 1."""

    _attr_icon = "mdi:minus-circle-outline"

    @property
    def unique_id(self) -> str:
        return f"{self._counter_id}_decrement"

    @property
    def name(self) -> str:
        return "Decrement"

    async def async_press(self) -> None:
        """Decrement the counter by 1."""
        try:
            await self.coordinator.client.decrement(self._counter_id, 1)
            await self.coordinator.async_request_refresh()
        except CountTogetherApiError as err:
            _LOGGER.error("Failed to decrement counter %s: %s", self._counter_id, err)

