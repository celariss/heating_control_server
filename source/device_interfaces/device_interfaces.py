__author__      = "Jérôme Cuq"

from .mqtt_device_interface import MQTTDeviceInterface
from .device_interface_callbacks import DeviceInterfaceCallbacks
from protocols.mqtt_protocol_handler import MQTTProtocolHandler
from device import Device

import logging

# This class manages communication with devices
class DeviceInterfaces:
    def __init__(self, callbacks:DeviceInterfaceCallbacks):
        self.logger: logging.Logger = logging.getLogger('hcs.devint')
        self.interfaces:dict = {}
        # Only MQTT so far
        MQTT = MQTTProtocolHandler.get_config_type()
        self.interfaces[MQTT] = MQTTDeviceInterface(callbacks)

    def on_client_connect(self, protocol_type: str, client_name: str):
        self.interfaces[protocol_type].on_client_connect(client_name)

    def on_client_disconnect(self, protocol_type: str, client_name: str):
        self.interfaces[protocol_type].on_client_disconnect(client_name)

    def on_client_message(self, protocol_type: str, client_name: str, message):
        self.interfaces[protocol_type].on_client_message(client_name, message)

    def on_server_alive_for_client(self, protocol_type: str, client_name: str, is_alive:bool):
        self.interfaces[protocol_type].on_server_alive_for_client(client_name, is_alive)

    def on_server_alive(self, is_alive:bool):
        for item in self.interfaces.values():
            item.on_server_alive(is_alive)

    # Ask for a device parameter change
    # param_name may be either :
    # - 'setpoint' : param_value must be a float.
    def set_device_parameter(self, device: Device, param_name, param_value):
        if param_name not in ['setpoint']:
            self.logger.error("set_device_parameter() : invalid param_name '"+param_name+"'")
        else:
            self.interfaces[device.protocol_type].set_device_parameter(device, param_name, param_value)