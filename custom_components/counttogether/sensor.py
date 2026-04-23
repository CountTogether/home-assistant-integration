"""Sensor entities for CountTogether."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    COUNTER_TYPE_UPDOWN,
    COUNTER_TYPE_FROM_DATE,
    COUNTER_TYPE_TO_DATE,
)
from .coordinator import CountTogetherCoordinator

_LOGGER = logging.getLogger(__name__)

_VALUE_ICONS: dict[str, str] = {
    COUNTER_TYPE_UPDOWN: "mdi:counter",
    COUNTER_TYPE_FROM_DATE: "mdi:calendar-clock",
    COUNTER_TYPE_TO_DATE: "mdi:calendar-arrow-right",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CountTogether sensors from a config entry."""
    coordinator: CountTogetherCoordinator = hass.data[DOMAIN][entry.entry_id]

    known_ids: set[str] = set()

    @callback
    def _add_new_entities() -> None:
        if coordinator.data is None:
            return
        new_entities: list[SensorEntity] = []
        for counter_id, counter in coordinator.data.items():
            if counter_id in known_ids:
                continue
            known_ids.add(counter_id)
            counter_type = counter.get("type", COUNTER_TYPE_UPDOWN)

            new_entities.append(CounterValueSensor(coordinator, counter_id))

            if counter_type == COUNTER_TYPE_FROM_DATE:
                new_entities.append(CounterStartDateSensor(coordinator, counter_id))
            elif counter_type == COUNTER_TYPE_TO_DATE:
                new_entities.append(CounterEndDateSensor(coordinator, counter_id))

        if new_entities:
            async_add_entities(new_entities)

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class _CounterBaseSensor(CoordinatorEntity[CountTogetherCoordinator], SensorEntity):
    """Base class for CountTogether sensor entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CountTogetherCoordinator, counter_id: str) -> None:
        # Set counter_id BEFORE super().__init__() so unique_id is available immediately
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


class CounterValueSensor(_CounterBaseSensor):
    """Sensor representing the current value of a counter."""

    @property
    def unique_id(self) -> str:
        return f"{self._counter_id}_value"

    @property
    def name(self) -> str:
        return "Value"

    @property
    def icon(self) -> str:
        counter = self._counter
        if counter is None:
            return "mdi:counter"
        return _VALUE_ICONS.get(counter.get("type", COUNTER_TYPE_UPDOWN), "mdi:counter")

    @property
    def state(self) -> int | None:
        counter = self._counter
        if counter is None:
            return None
        return counter.get("value")

    @property
    def state_class(self) -> SensorStateClass:
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str | None:
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        counter = self._counter or {}
        return {
            "counter_id": self._counter_id,
            "counter_type": counter.get("type"),
            "counter_name": counter.get("name"),
            "created": counter.get("created"),
        }


class CounterStartDateSensor(_CounterBaseSensor):
    """Sensor representing the start date of a FromDate counter."""

    _attr_icon = "mdi:calendar-start"
    _attr_device_class = SensorDeviceClass.DATE

    @property
    def unique_id(self) -> str:
        return f"{self._counter_id}_start_date"

    @property
    def name(self) -> str:
        return "Start Date"

    @property
    def state(self) -> str | None:
        counter = self._counter
        if counter is None:
            return None
        return counter.get("startDate")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        counter = self._counter or {}
        return {
            "counter_id": self._counter_id,
            "counter_name": counter.get("name"),
        }


class CounterEndDateSensor(_CounterBaseSensor):
    """Sensor representing the end date of a ToDate counter."""

    _attr_icon = "mdi:calendar-end"
    _attr_device_class = SensorDeviceClass.DATE

    @property
    def unique_id(self) -> str:
        return f"{self._counter_id}_end_date"

    @property
    def name(self) -> str:
        return "End Date"

    @property
    def state(self) -> str | None:
        counter = self._counter
        if counter is None:
            return None
        return counter.get("endDate")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        counter = self._counter or {}
        return {
            "counter_id": self._counter_id,
            "counter_name": counter.get("name"),
        }
