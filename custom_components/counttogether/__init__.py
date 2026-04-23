"""The CountTogether integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CountTogetherClient
from .const import DOMAIN, CONF_API_TOKEN
from .coordinator import CountTogetherCoordinator
from .services import async_register_services, async_unregister_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CountTogether from a config entry."""
    session = async_get_clientsession(hass)
    client = CountTogetherClient(
        api_token=entry.data[CONF_API_TOKEN],
        session=session,
        timezone=hass.config.time_zone,
    )

    coordinator = CountTogetherCoordinator(hass, client)

    # Register services early so they're always available
    if not hass.services.has_service(DOMAIN, "increment"):
        async_register_services(hass)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start WebSocket listener for real-time updates
    await coordinator.async_start_websocket()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: CountTogetherCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_stop_websocket()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    if not hass.data[DOMAIN]:
        async_unregister_services(hass)

    return unload_ok
