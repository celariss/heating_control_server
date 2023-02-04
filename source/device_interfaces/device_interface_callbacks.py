__author__      = "Jérôme Cuq"

from device import *

class DeviceInterfaceCallbacks:
    def get_devices(self) -> dict[str,Device]:
        pass

    def on_device_state(self, device:Device, available:bool):
        pass

    def on_device_current_temperature(self, device:Device, value:float):
        pass

    def on_device_setpoint(self, device:Device, value:float):
        pass
    
    # protocol_msg_params content depends on the protocol handler implementation
    def send_message_to_device(self, device:Device, protocol_msg_params):
        pass