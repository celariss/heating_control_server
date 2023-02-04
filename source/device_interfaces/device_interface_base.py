__author__      = "Jérôme Cuq"

from .device_interface_callbacks import DeviceInterfaceCallbacks
import device

class DeviceInterfaceBase:
    def __init__(self, callbacks:DeviceInterfaceCallbacks):
        pass
    
    def on_client_connect(self, client_name: str):
        pass
    
    def on_client_disconnect(self, client_name: str):
        pass

    def on_client_message(self, client_name: str, message):
        pass

    def on_server_alive(self, client_name: str, is_alive:bool):
        pass

    # Ask for a device parameter change
    # The implementation is in charge of sending command via DeviceInterfaceCallbacks
    # param_name may be either :
    # - 'setpoint' : param_value must be a float.
    def set_device_parameter(self, device: device.Device, param_name, param_value):
        pass