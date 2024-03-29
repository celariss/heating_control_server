from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant import config_entries

from .const import (
    DOMAIN,
    DATA_CONFIG,
    DATA_SERVER,
)

# Internal definitions
_LOGGER = logging.getLogger(__name__)

# __package__ == custom_components.heating_control_srv
from pathlib import Path
import sys
DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))
from heating_control_server.controller import Controller
from heating_control_server.errors import CfgError

   

# (deprecated) @asyncio.coroutine
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Setup our skeleton component."""
    _LOGGER.debug("%s.async_setup()",DOMAIN)
    
    # States are in the format DOMAIN.OBJECT_ID.
    #hass.states.async_set(DOMAIN+'.server', 'OK')
    
    hass.data[DOMAIN] = {}

    # Save the config in HA
    if DOMAIN in config:
        hass.data[DOMAIN][DATA_CONFIG] = config[DOMAIN]
        """ _LOGGER.info('starting Controller_')
        heating_control_server = Controller('/config/', 'heating_ctrl_')
        try:
            heating_control_server.start()
        except CfgError as exc:
            _LOGGER.error("Could not start heating server : "+exc.generic_desc,DOMAIN)
            heating_control_server.stop()
            heating_control_server = None
        hass.data[DOMAIN][DATA_SERVER] = heating_control_server """

    # Return boolean to indicate that initialization was successfull.
    return True
    
    
async def async_setup_entry(hass: HomeAssistant, config_entry: config_entries.ConfigEntry) -> bool:
    """Set up integration from a config entry (TBD i.e. registered device ?).
    Will automatically load components to support devices (TBD previously ?) found on the network.
    """
    _LOGGER.debug("%s.async_setup_entry()",DOMAIN)

    # Get the configuration stored in HA for this integration
    ha_data = hass.data.setdefault(DOMAIN, {})
    config = ha_data.get(DATA_CONFIG, {})

    hass_data = dict(config_entry.data)
    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = config_entry.add_update_listener(options_update_listener)
    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener
    hass.data[DOMAIN][config_entry.entry_id] = hass_data
    
    _LOGGER.info('starting Controller')
    heating_control_server = Controller('/config/', 'heating_ctrl_')
    try:
        heating_control_server.start()
    except CfgError as exc:
        _LOGGER.error("Could not start heating server : "+exc.generic_desc,DOMAIN)
        heating_control_server.stop()
        heating_control_server = None
    hass.data[DOMAIN][DATA_SERVER] = heating_control_server
    
    return True
    
async def async_unload_entry(hass, entry):
    """Unload config entry."""
    _LOGGER.debug("%s.async_unload_entry()",DOMAIN)
    
    # called when an integration instance is removed from HA
    _LOGGER.info('stopping Controller')
    if hass.data[DOMAIN][DATA_SERVER]:
        hass.data[DOMAIN][DATA_SERVER].stop()

    # Remove options_update_listener.
    hass.data[DOMAIN][entry.entry_id]["unsub_options_update_listener"]()

    # Remove config entry from domain.
    hass.data[DOMAIN].pop(entry.entry_id)

    return True
    
async def async_migrate_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Migrate old entry to current entry format."""
    _LOGGER.debug("Migrating entry from configuration version %s", config_entry.version)
    # TBD when configuration params list changes
    
async def options_update_listener(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
):
    _LOGGER.debug("%s.options_update_listener()",DOMAIN)
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)