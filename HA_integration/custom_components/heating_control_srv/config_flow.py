"""Config flow for RF Player integration."""
from __future__ import annotations
from typing import Any
import logging
import serial
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE, CONF_DEVICES
from homeassistant.components import usb
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_TEST,
    TITLE,
)

# Internal definitions
_LOGGER = logging.getLogger(__name__)

# True for debug on local VSCode devcontainer without dongle
_DEVICE_IS_MANDATORY = False


"""
Build the configuration schema to be shown to the user
return a tuple : (config_schema, devices_description, devices_path) where :
    devices_description : contains a user friendly description of each serial connected device
    devices_path : contains the path of each serial device, in the same order
"""
def build_config_schema(default_options:dict = {}) -> vol.Schema:
    # Data schema representing the integration configuration
    config_schema:dict = {}
    #config_schema[vol.Required(CONF_TEST, default=default_options.get(CONF_TEST,"*"))] = vol.unicode
    return vol.Schema(config_schema)

"""
Does the job of going through the configuration process,
for initial configuration flow and any subsequent options flows (code is almost the same)
"""
def config_step(flowObject : config_entries.ConfigFlow, user_input, initial_config : bool):
    # During reconfiguration process (options form), we need to use the current configuration
    # as default values for the schema
    if initial_config: default_options = {}
    else: default_options = flowObject.config_entry.data
    config_schema:vol.Schema = build_config_schema(default_options)

    # When the user validate the config form, this step is called with the user_input content
    errors = {}
    if user_input is not None:
        # TBD
        if not errors:
            _LOGGER.info(f"{'Initial configuration' if initial_config else 'Configuration changed'}")

            if not initial_config:
                # we update the integration data to reflect changes made by the user
                # TBD

                # we update the config data in HA with the new data
                flowObject.config_entry.data = user_input

            return flowObject.async_create_entry(
                    title=TITLE,
                    data=user_input,
        )

    # We can get here for 2 reasons :
    # 1- At first call of this step (there is no user input yet)
    #    -> we must provide default config and show config form
    # 2- Each time the user_input provided lead to an error

    # Now we can call the form to the user
    return flowObject.async_show_form(
        step_id="user" if initial_config else "init",
        data_schema=config_schema,
        errors=errors
    )

"""
HA Entry point for configuration/options process
"""
class HCSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize flow instance."""
        # TBD

    async def async_step_user(self, user_input=None):
        """Handle config flow initial step.
        This goes through the steps to take the user through the setup process.
        Using this it is possible to update the UI and prompt for additional
        information."""
        _LOGGER.debug("%s.HCSConfigFlow.async_step_user()",DOMAIN)

        # Allow the use of only one heating control server in HA
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return config_step(self, user_input, True)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return HCSOptionsFlow(config_entry)


class HCSOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        _LOGGER.debug("%s.HCSOptionsFlow.async_step_init()",DOMAIN)

        return config_step(self, user_input, False)
