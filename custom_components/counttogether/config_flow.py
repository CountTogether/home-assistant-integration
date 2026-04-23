"""Config flow for CountTogether integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CountTogetherClient, CountTogetherApiError, CountTogetherAuthError
from .const import DOMAIN, CONF_API_TOKEN, CONF_TIMEZONE

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
    }
)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input and return info to store."""
    session = async_get_clientsession(hass)
    client = CountTogetherClient(
        api_token=data[CONF_API_TOKEN],
        session=session,
        timezone=hass.config.time_zone,
    )
    counters = await client.list_counters()
    return {"title": f"CountTogether ({len(counters)} counter(s))"}


class CountTogetherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CountTogether."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await _validate_input(self.hass, user_input)
            except CountTogetherAuthError:
                errors["base"] = "invalid_auth"
            except CountTogetherApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during CountTogether setup")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_API_TOKEN][:16])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication."""
        return await self.async_step_user(user_input)

