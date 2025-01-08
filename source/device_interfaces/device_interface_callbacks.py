__author__      = "Jérôme Cuq"

from device import *

class DeviceInterfaceCallbacks:
    ### All the following notification functions must be called on received change on any device
    ### currently in configuration
    def on_device_state(self, device:Device, available:bool):
        pass

    def on_device_current_temperature(self, device:Device, value:float):
        pass

    def on_device_min_temperature(self, device:Device, value:float):
        pass

    def on_device_max_temperature(self, device:Device, value:float):
        pass

    def on_device_setpoint(self, device:Device, previousValue:float):
        pass

    def on_discovered_device(self, device:Device):
        pass

    def get_protocol_type_from_name(self, client_name: str) -> str:
        pass
    
    # protocol_msg_params content depends on the protocol handler implementation
    def send_message_to_device(self, device:Device, protocol_msg_params:dict):
        pass

    def send_message_to_client(self, protocol_type:str, client_name:str, protocol_msg_params:dict):
        pass