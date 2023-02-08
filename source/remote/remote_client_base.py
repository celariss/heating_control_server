__author__      = "Jérôme Cuq"

from device import Device
from .remote_control_callbacks import RemoteControlCallbacks

class RemoteClientBase:
    def __init__(self, remote_name:str, config_remote_client: dict, devices: dict[str,Device], callbacks:RemoteControlCallbacks):
        """_summary_

        :param remote_name: _description_
        :type remote_name: str
        :param config_remote_client: _description_
        :type config_remote_client: dict
        :param devices: _description_
        :type devices: dict[str,Device]
        :param callbacks: _description_
        :type callbacks: RemoteControlCallbacks
        :raises CfgError: in case of error in protocol settings
        """
        pass

    def get_name(self) -> str:
        pass

    ## return the name of the connexion client
    def get_client_name(self) -> str:
        pass

    def on_client_connect(self):
        pass

    def on_client_disconnect(self):
        pass

    def on_server_alive(self, is_alive:bool):
        pass

    def on_client_message(self, message):
        pass

    def on_device_state(self, device_name:str, available:bool):
        pass

    def on_device_current_temperature(self, device_name:str, value:float):
        pass

    def on_device_setpoint(self, device_name:str, value:float):
        pass

    def on_scheduler(self, scheduler_config:dict):
        pass

    def on_devices(self, devices:dict[str,Device]):
        pass

    def on_server_response(self, status:str, error:dict=None):
        pass
