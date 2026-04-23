"""Services for the CountTogether integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .api import CountTogetherApiError
from .const import (
    DOMAIN,
    SERVICE_INCREMENT,
    SERVICE_DECREMENT,
    SERVICE_SET_VALUE,
    SERVICE_SET_START_DATE,
    SERVICE_SET_END_DATE,
    ATTR_AMOUNT,
    ATTR_VALUE,
    ATTR_START_DATE,
    ATTR_END_DATE,
    COUNTER_TYPE_UPDOWN,
    COUNTER_TYPE_FROM_DATE,
    COUNTER_TYPE_TO_DATE,
)
from .coordinator import CountTogetherCoordinator

_LOGGER = logging.getLogger(__name__)

# Services are invoked with a `target:` selector; HA populates one or more
# of the target keys. Accept all three and make them optional.
_TARGET_SCHEMA = {
    vol.Optional(ATTR_ENTITY_ID): vol.Any(cv.entity_ids, None),
    vol.Optional(ATTR_DEVICE_ID): vol.Any(vol.All(cv.ensure_list, [cv.string]), None),
    vol.Optional("area_id"): vol.Any(vol.All(cv.ensure_list, [cv.string]), None),
}

INCREMENT_SCHEMA = vol.Schema(
    {
        **_TARGET_SCHEMA,
        vol.Optional(ATTR_AMOUNT, default=1): vol.All(int, vol.Range(min=1)),
    }
)
DECREMENT_SCHEMA = vol.Schema(
    {
        **_TARGET_SCHEMA,
        vol.Optional(ATTR_AMOUNT, default=1): vol.All(int, vol.Range(min=1)),
    }
)
SET_VALUE_SCHEMA = vol.Schema(
    {
        **_TARGET_SCHEMA,
        vol.Required(ATTR_VALUE): int,
    }
)
SET_START_DATE_SCHEMA = vol.Schema(
    {
        **_TARGET_SCHEMA,
        vol.Required(ATTR_START_DATE): cv.string,
    }
)
SET_END_DATE_SCHEMA = vol.Schema(
    {
        **_TARGET_SCHEMA,
        vol.Required(ATTR_END_DATE): cv.string,
    }
)


def _get_coordinator(hass: HomeAssistant) -> CountTogetherCoordinator:
    """Return the first available coordinator."""
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise HomeAssistantError("No CountTogether integration configured.")
    return next(iter(entries.values()))


def _counter_id_from_device(device) -> str | None:
    """Extract counter_id from a device's identifiers."""
    if device is None:
        return None
    for domain, identifier in device.identifiers:
        if domain == DOMAIN:
            return identifier
    return None


def _resolve_counter_ids(hass: HomeAssistant, call: ServiceCall) -> list[str]:
    """Resolve entity/device/area targets to CountTogether counter_ids."""
    entity_ids: list[str] = list(call.data.get(ATTR_ENTITY_ID) or [])
    device_ids: list[str] = list(call.data.get(ATTR_DEVICE_ID) or [])
    area_ids: list[str] = list(call.data.get("area_id") or [])

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    counter_ids: list[str] = []
    seen: set[str] = set()

    def _add(counter_id: str | None) -> None:
        if counter_id and counter_id not in seen:
            seen.add(counter_id)
            counter_ids.append(counter_id)

    # Resolve entities → either via state attribute or via their device.
    for entity_id in entity_ids:
        resolved: str | None = None
        state = hass.states.get(entity_id)
        if state is not None:
            resolved = state.attributes.get("counter_id")
        if not resolved:
            entry = ent_reg.async_get(entity_id)
            if entry and entry.device_id:
                resolved = _counter_id_from_device(dev_reg.async_get(entry.device_id))
        if not resolved:
            raise HomeAssistantError(
                f"Entity '{entity_id}' is not a CountTogether counter."
            )
        _add(resolved)

    # Resolve explicitly selected devices.
    for device_id in device_ids:
        counter_id = _counter_id_from_device(dev_reg.async_get(device_id))
        if not counter_id:
            raise HomeAssistantError(
                f"Device '{device_id}' is not a CountTogether counter."
            )
        _add(counter_id)

    # Resolve areas → all CountTogether devices in the area.
    if area_ids:
        for device in dev_reg.devices.values():
            if device.area_id in area_ids:
                _add(_counter_id_from_device(device))

    if not counter_ids:
        raise HomeAssistantError(
            "No CountTogether counter selected. Please choose a device or a "
            "CountTogether sensor as the target."
        )
    return counter_ids


def _filter_by_type(
    coordinator: CountTogetherCoordinator,
    counter_ids: list[str],
    allowed_types: tuple[str, ...],
    action: str,
) -> list[str]:
    """Return only counter_ids matching the allowed types, raise if none match."""
    data = coordinator.data or {}
    valid: list[str] = []
    skipped: list[str] = []
    for counter_id in counter_ids:
        counter = data.get(counter_id)
        if counter is None:
            skipped.append(counter_id)
            continue
        if counter.get("type") in allowed_types:
            valid.append(counter_id)
        else:
            skipped.append(
                f"{counter.get('name', counter_id)} ({counter.get('type')})"
            )
    if not valid:
        raise HomeAssistantError(
            f"Cannot {action}: selected counter(s) are not of type "
            f"{', '.join(allowed_types)}. Skipped: {', '.join(skipped) or 'unknown'}."
        )
    if skipped:
        _LOGGER.warning(
            "Skipping counters for action %s (wrong type): %s",
            action,
            ", ".join(skipped),
        )
    return valid


def async_register_services(hass: HomeAssistant) -> None:
    """Register CountTogether services."""

    async def handle_increment(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        counter_ids = _filter_by_type(
            coordinator,
            _resolve_counter_ids(hass, call),
            (COUNTER_TYPE_UPDOWN,),
            "increment",
        )
        amount: int = call.data.get(ATTR_AMOUNT, 1)
        try:
            for counter_id in counter_ids:
                new_value = await coordinator.client.increment(counter_id, amount)
                _LOGGER.debug(
                    "Incremented %s by %s -> %s", counter_id, amount, new_value
                )
            await coordinator.async_request_refresh()
        except CountTogetherApiError as err:
            raise HomeAssistantError(f"Failed to increment counter: {err}") from err

    async def handle_decrement(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        counter_ids = _filter_by_type(
            coordinator,
            _resolve_counter_ids(hass, call),
            (COUNTER_TYPE_UPDOWN,),
            "decrement",
        )
        amount: int = call.data.get(ATTR_AMOUNT, 1)
        try:
            for counter_id in counter_ids:
                new_value = await coordinator.client.decrement(counter_id, amount)
                _LOGGER.debug(
                    "Decremented %s by %s -> %s", counter_id, amount, new_value
                )
            await coordinator.async_request_refresh()
        except CountTogetherApiError as err:
            raise HomeAssistantError(f"Failed to decrement counter: {err}") from err

    async def handle_set_value(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        counter_ids = _filter_by_type(
            coordinator,
            _resolve_counter_ids(hass, call),
            (COUNTER_TYPE_UPDOWN,),
            "set value",
        )
        value: int = call.data[ATTR_VALUE]
        try:
            for counter_id in counter_ids:
                await coordinator.client.patch_counter(counter_id, value=value)
            await coordinator.async_request_refresh()
        except CountTogetherApiError as err:
            raise HomeAssistantError(f"Failed to set counter value: {err}") from err

    async def handle_set_start_date(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        counter_ids = _filter_by_type(
            coordinator,
            _resolve_counter_ids(hass, call),
            (COUNTER_TYPE_FROM_DATE,),
            "set start date",
        )
        start_date: str = call.data[ATTR_START_DATE]
        try:
            for counter_id in counter_ids:
                await coordinator.client.patch_counter(
                    counter_id, start_date=start_date
                )
            await coordinator.async_request_refresh()
        except CountTogetherApiError as err:
            raise HomeAssistantError(f"Failed to set start date: {err}") from err

    async def handle_set_end_date(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        counter_ids = _filter_by_type(
            coordinator,
            _resolve_counter_ids(hass, call),
            (COUNTER_TYPE_TO_DATE,),
            "set end date",
        )
        end_date: str = call.data[ATTR_END_DATE]
        try:
            for counter_id in counter_ids:
                await coordinator.client.patch_counter(counter_id, end_date=end_date)
            await coordinator.async_request_refresh()
        except CountTogetherApiError as err:
            raise HomeAssistantError(f"Failed to set end date: {err}") from err

    hass.services.async_register(
        DOMAIN, SERVICE_INCREMENT, handle_increment, schema=INCREMENT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DECREMENT, handle_decrement, schema=DECREMENT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_VALUE, handle_set_value, schema=SET_VALUE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_START_DATE, handle_set_start_date, schema=SET_START_DATE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_END_DATE, handle_set_end_date, schema=SET_END_DATE_SCHEMA
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister CountTogether services."""
    for service in (
        SERVICE_INCREMENT,
        SERVICE_DECREMENT,
        SERVICE_SET_VALUE,
        SERVICE_SET_START_DATE,
        SERVICE_SET_END_DATE,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)

