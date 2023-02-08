__author__      = "Jérôme Cuq"

from .device_interface_callbacks import DeviceInterfaceCallbacks
import device

class DeviceInterfaceBase:
    def __init__(self, devices: dict[str,device.Device], auto_discovery: list[dict], callbacks:DeviceInterfaceCallbacks):
        """The constructor must check :
        - the protocol_params of each device 
        - auto_discovery content
        It must raise CfgError if necessary

        :param devices: all devices that are related to the protocol handled by this instance
        :type devices: dict[str,device.Device]
        :param auto_discovery: auto_discovery parameters that are related to the protocol handled by this instance
        :type auto_discovery: list[dict]
        :param callbacks: Callback to the controller
        :type callbacks: DeviceInterfaceCallbacks
        :raises CfgError: in case of error in auto_discovery or device.protocol_params format
        """
        pass
    
    def on_client_connect(self, client_name: str):
        pass
    
    def on_client_disconnect(self, client_name: str):
        pass

    def on_client_message(self, client_name: str, message):
        pass

    def on_server_alive(self, client_name: str, is_alive:bool):
        pass

    def on_devices(self, devices:dict[str,device.Device]):
        pass

    # Ask for a device parameter change
    # The implementation is in charge of sending command via DeviceInterfaceCallbacks
    # param_name may be either :
    # - 'setpoint' : param_value must be a float.
    def set_device_parameter(self, device: device.Device, param_name, param_value):
        pass