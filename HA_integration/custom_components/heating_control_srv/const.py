"""All constants related to the ZHA component."""
from __future__ import annotations
import voluptuous as vol

# imports for all supported platforms
from homeassistant.components.sensor import DOMAIN as SENSOR



# The domain of your component. Should be equal to the name of your component.
DOMAIN = "heating_control_srv"
DATA_CONFIG = "config"
DATA_SERVER = "server_instance"
TITLE = "HeatingControlServerInstance"

# String IDs used by config_flow
# Each ID must be defined in strings.json
CONF_TEST = "test"
