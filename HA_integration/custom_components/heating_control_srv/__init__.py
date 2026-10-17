from __future__ import annotations

import asyncio
import logging

from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant import config_entries
from homeassistant.components import mqtt
#from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.event import async_track_state_change_filtered, TrackStates

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

    # Check that MQTT component is available
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("The MQTT broker is not available")
        return False

    # Function called when a change is detected on a climate entity in HA
    # The goal here is to get the new state of the climate entity and forward it to the heating control GUI via MQTT,
    # by publishing the new state on the topic 'homeassistant/climate/my_climate/*'
    async def _state_changed_listener(event: Event[EventStateChangedData]):
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        entity_id = event.data.get("entity_id")
        
        # Only filter on entities of the 'climate' domain
        if entity_id.startswith("climate."):
            if new_state is not None:
                entity_id = entity_id.split('.')[1]
                for key in new_state.attributes:
                    if (old_state is None) or (not key in old_state.attributes) or (old_state.attributes[key] != new_state.attributes[key]):
                        topic = f"homeassistant/climate/{entity_id}/{key}"
                        # Publish the new attribute on MQTT
                        await mqtt.async_publish(hass, topic, new_state.attributes[key], retain=True)
                if (old_state is None) or old_state.state != new_state.state:
                    topic = f"homeassistant/climate/{entity_id}/state"
                    await mqtt.async_publish(hass, topic, new_state.state, retain=True)
                if (old_state is None) or old_state.last_updated != new_state.last_updated:
                    topic = f"homeassistant/climate/{entity_id}/last_updated"
                    await mqtt.async_publish(hass, topic, new_state.last_updated, retain=True)
            else:
                # Entity has been removed, remove topic on MQTT
                discovery_topic = f"homeassistant/climate/{entity_id}"
                # To be tested
                #mqtt.async_publish(hass, discovery_topic, "", retain=True)

     # Getting all "initial" states of all climate entities
    all_states = hass.states.async_all()
    entites_climate = [state for state in all_states if state.domain == "climate"]
    # Publishing all initial states of all climate entities to MQTT
    for state in entites_climate:
        await _state_changed_listener( Event("state_changed", {"entity_id": state.entity_id, "old_state": None, "new_state": state}) )

    # Tracks everything in the 'climate' domain
    track_filter = TrackStates(
        all_states=True, 
        entities=set(), 
        domains={"climate"}
    )

    # Listening for state changes on all climate entities
    unsub = async_track_state_change_filtered(hass, track_filter, _state_changed_listener)

    # Function called when an MQTT message is received on the topic
    # The goal here is to get a setpoint change request from the heating control GUI and forward it to the corresponding climate entity in HA, 
    # by calling the HA service 'climate.set_temperature'
    async def async_mqtt_message_received(msg):
        """Process the received MQTT message."""
        payload = msg.payload
        topic = msg.topic
        
        # Extract the climate name from the topic : 'homeassistant/climate/my_climate/new_setpoint'
        parts = topic.split('/')
        if len(parts) >= 3:
            entity_name = parts[2]
            target_entity_id = f"climate.{entity_name}"

            try:
                temperature = float(payload)
                _LOGGER.info(
                    "Received MQTT setpoint for %s : %s°C", target_entity_id, temperature
                )

                # Call the climate.set_temperature service directly in Python
                await hass.services.async_call(
                    domain="climate",
                    service="set_temperature",
                    service_data={
                        "entity_id": target_entity_id,
                        "temperature": temperature,
                        "hvac_mode": "heat",
                    },
                    blocking=True,
                )
            except ValueError:
                _LOGGER.error("Invalid temperature payload : %s", payload)

    # Subscription (subscribe) to the wildcard MQTT topic
    await mqtt.async_subscribe(
        hass,
        "homeassistant/climate/+/new_setpoint",
        async_mqtt_message_received,
    )

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