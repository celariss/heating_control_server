__author__      = "Jérôme Cuq"

from .remote_control_callbacks import RemoteControlCallbacks
from .mqtt_remote_client import MQTTRemoteClient
from .remote_client_base import RemoteClientBase
from protocols.mqtt_protocol_handler import MQTTProtocolHandler

import logging


class RemoteControl:
    def __init__(self, config_remote_control, callbacks:RemoteControlCallbacks):
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
                remote = MQTTRemoteClient(remote_name, config_remote, callbacks.get_client_by_name(client_name), callbacks)
            else:
                self.logger.error("Invalid configuration for remote_control '"+protocol_type+"': unknown protocol type '"+protocol_type+"'")
                return
            self.remotes[remote_name] = remote

    ### return list of all remotes that use the connection client 'client_name'
    def get_remotes_by_client_name(self, client_name:str) -> list:
        res:list = []
        for name in self.remotes:
            if self.remotes[name].get_client_name()==client_name:
                res.append(self.remotes[name])
        return res

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
        for name in self.remotes:
            self.remotes[name].on_device_state(device_name, available)

    def on_device_current_temperature(self, device_name:str, value:float):
        for name in self.remotes:
            self.remotes[name].on_device_current_temperature(device_name, value)

    def on_device_setpoint(self, device_name, value:float):
        for name in self.remotes:
            self.remotes[name].on_device_setpoint(device_name, value)

    def on_scheduler(self, scheduler_config:dict):
        for name in self.remotes:
            self.remotes[name].on_scheduler(scheduler_config)

    def on_server_response(self, remote_name:str, status:str, error:dict=None):
        self.logger.info("Sending server response to remote '"+remote_name+"' : status="+status+(", error="+str(error) if error else ""));
        if remote_name in self.remotes:
            self.remotes[remote_name].on_server_response(status, error)