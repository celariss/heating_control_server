__author__      = "Jérôme Cuq"

from device import Device
from .remote_control_callbacks import RemoteControlCallbacks
from .mqtt_remote_client import MQTTRemoteClient
from .remote_client_base import RemoteClientBase
from protocols.mqtt_protocol_handler import MQTTProtocolHandler

import logging


class RemoteControl:
    def __init__(self, config_remote_control, devices: dict[str,Device], available_devices: dict[str, Device], callbacks:RemoteControlCallbacks):
        """
        :param config_remote_control: _description_
        :type config_remote_control: _type_
        :param devices: _description_
        :type devices: dict[str,Device]
        :param callbacks: _description_
        :type callbacks: RemoteControlCallbacks
        :raises CfgError: in case of error in protocol settings
        """
        self.logger: logging.Logger = logging.getLogger('hcs.remotecontrol')
        self.config_remote_control: dict = config_remote_control
        self.callbacks = callbacks
        self.remotes: dict[str,RemoteClientBase] = {}
        for config_remote in self.config_remote_control:
            remote_name = config_remote['name']
            client_name = config_remote['protocol']['name']
            protocol_type = callbacks.get_protocol_type_from_name(client_name)
            # Only MQTT protocol is known so far
            if protocol_type == MQTTProtocolHandler.get_config_type():
                remote = MQTTRemoteClient(remote_name, config_remote, callbacks.get_client_by_name(client_name), devices, available_devices, callbacks)
            else:
                self.logger.error("Invalid configuration for remote_control '"+protocol_type+"': unknown protocol type '"+protocol_type+"'")
                return
            self.remotes[remote_name] = remote

    def start(self):
        for remote in self.remotes.values():
            remote.start()
        self.on_server_alive(True)

    def stop(self):
        self.on_server_alive(False)
        for remote in self.remotes.values():
            remote.stop()

    ### return list of all remotes that use the connection client 'client_name'
    def get_remotes_by_client_name(self, client_name:str) -> list:
        res:list = []
        for name in self.remotes:
            if self.remotes[name].get_client_name()==client_name:
                res.append(self.remotes[name])
        return res
    
    ## send current device data to all clients
    def send_device_data(self, device_name: str):
        for name in self.remotes:
            self.remotes[name].send_device_data(device_name)

    def on_client_connect(self, client_name):
        for remote in self.get_remotes_by_client_name(client_name):
            remote.on_client_connect()

    def on_client_disconnect(self, client_name):
        for remote in self.get_remotes_by_client_name(client_name):
            remote.on_client_disconnect()

    def on_client_message(self, client_name: str, message):
        for remote in self.get_remotes_by_client_name(client_name):
            remote.on_client_message(message)

    def on_server_alive(self, is_alive:bool):
        for remote in self.remotes.values():
            remote.on_server_alive(is_alive)

    def on_server_alive_for_client(self, client_name: str, is_alive:bool):
        for remote in self.get_remotes_by_client_name(client_name):
            remote.on_server_alive(is_alive)

    def on_device_state(self, device_name:str, available:bool):
        for remote in self.remotes.values():
            remote.on_device_state(device_name, available)

    def on_device_current_temperature(self, device_name:str, value:float):
        for remote in self.remotes.values():
            remote.on_device_current_temperature(device_name, value)

    def on_device_min_temperature(self, device_name:str, value:float):
        for remote in self.remotes.values():
            remote.on_device_min_temperature(device_name, value)

    def on_device_max_temperature(self, device_name:str, value:float):
        for remote in self.remotes.values():
            remote.on_device_max_temperature(device_name, value)

    def on_device_setpoint(self, device_name, value:float):
        for remote in self.remotes.values():
            remote.on_device_setpoint(device_name, value)

    def on_scheduler(self, scheduler_config:dict):
        for remote in self.remotes.values():
            remote.on_scheduler(scheduler_config)

    def on_devices(self, devices:dict[str,Device]):
        for remote in self.remotes.values():
            remote.on_devices(devices)

    def on_available_devices(self, devices:dict[str,Device]):
        for remote in self.remotes.values():
            remote.on_available_devices(devices)

    def on_server_response(self, remote_name:str, status:str, error:dict=None):
        self.logger.info("Sending server response to remote '"+remote_name+"' : status="+status+(", error="+str(error) if error else ""));
        if remote_name in self.remotes:
            self.remotes[remote_name].on_server_response(status, error)