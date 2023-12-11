__author__      = "Jérôme Cuq"

from device_interfaces.device_interface_base import DeviceInterfaceBase
from .mqtt_device_interface import MQTTDeviceInterface
from .device_interface_callbacks import DeviceInterfaceCallbacks
from protocols.mqtt_protocol_handler import MQTTProtocolHandler
from device import Device

import logging

class DeviceInterfaces:
    """
        This class manages communication with devices.
        It instanciates one device interface class for each protocol type.
    """
    def __init__(self, devices: dict[str,Device], auto_discovery:list[dict], callbacks:DeviceInterfaceCallbacks):
        """ctor for this class. Raises CfgError if some protocol settings are invalid

        :param devices: list of actual devices
        :type devices: dict[str,Device]
        :param auto_discovery: auto_discovery parameters
        :type auto_discovery: list[dict]
        :param callbacks: Callback to the controller
        :type callbacks: DeviceInterfaceCallbacks
        :raises CfgError: in case of error in auto_discovery or device.protocol_params format
        """
        self.logger: logging.Logger = logging.getLogger('hcs.devint')
        self.interfaces:dict[str,DeviceInterfaceBase] = {}
        self.callbacks = callbacks
        # Only MQTT so far
        MQTT = MQTTProtocolHandler.get_config_type()
        prot_auto_discovery = self.__get_auto_discovery(auto_discovery, MQTT)
        prot_devices = self.__get_devices(devices, MQTT)
        self.interfaces[MQTT] = MQTTDeviceInterface(prot_devices, prot_auto_discovery, callbacks)

    def __get_devices(self, devices: dict[str,Device], protocol:str) -> dict[str,Device]:
        prot_devices:dict[str,Device] = {}
        for item in devices.values():
            if item.protocol_type == protocol:
                prot_devices[item.name] = item
        return prot_devices

    def __get_auto_discovery(self, auto_discovery:list[dict], protocol:str) -> list:
        prot_auto_discovery:list = []
        if auto_discovery:
            for item in auto_discovery:
                if 'protocol_name' in item:
                    if self.callbacks.get_protocol_type_from_name(item['protocol_name']) == protocol:
                        prot_auto_discovery.append(item)
        return prot_auto_discovery

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

    def on_devices(self, devices:dict[str,Device]):
        for protocol in self.interfaces:
            #prot_devices = self.__get_devices(devices, protocol)
            self.interfaces[protocol].on_devices(devices)

    def on_available_devices(self, devices:dict[str,Device]):
        for protocol in self.interfaces:
            #prot_devices = self.__get_devices(devices, protocol)
            self.interfaces[protocol].on_available_devices(devices)

    # Ask for a device parameter change
    # param_name may be either :
    # - 'setpoint' : param_value must be a float.
    def set_device_parameter(self, device: Device, param_name:str, param_value):
        if param_name not in ['setpoint']:
            self.logger.error("set_device_parameter() : invalid param_name '"+param_name+"'")
        else:
            self.interfaces[device.protocol_type].set_device_parameter(device, param_name, param_value)