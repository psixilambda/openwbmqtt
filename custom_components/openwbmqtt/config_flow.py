"""The openwbmqtt component for controlling the openWB wallbox via home assistant / MQTT"""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.util import slugify

# Import global values.
from .const import DATA_SCHEMA, DOMAIN, MQTT_ROOT_TOPIC

##add optionshandler
@staticmethod
@callback
def async_get_options_flow(config_entry):
    return OpenWBOptionsFlowHandler(config_entry)

class openwbmqttConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configuration flow for the configuration of the openWB integration. When added by the user, he/she
    must provide configuration values as defined in DATA_SCHEMA."""

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        title = f"{user_input[MQTT_ROOT_TOPIC]}"
        # Abort if the same integration was already configured.
        await self.async_set_unique_id(title)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=title,
            data=user_input,
        )

class OpenWBOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "show_things",
                        default=self.config_entry.options.get("Add HouseBattery"),
                    ): bool
                }
            ),
        )
