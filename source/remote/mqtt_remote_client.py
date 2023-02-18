__author__ = "Jérôme Cuq"

import common
import json
import logging
import re
import paho.mqtt.client as mqtt
from configuration import Configuration
from device import Device
from protocols.mqttclient import MQTTClient
from .remote_client_base import RemoteClientBase
from .remote_control_callbacks import RemoteControlCallbacks
from errors import *


class MQTTRemoteClient(RemoteClientBase):
    def __init__(self, remote_name, config_remote_client, client: object, devices: dict[str, Device], callbacks: RemoteControlCallbacks):
        self.logger = logging.getLogger('hcs.mqttremoteclient')
        self.config_remote_client = config_remote_client
        self.devices: dict[str, Device] = devices
        self.callbacks = callbacks
        self.remote_name = remote_name
        self.config_protocol = config_remote_client['protocol']
        self.client_name = self.config_protocol['name']
        if not isinstance(client, MQTTClient):
            self.logger.error("Bad configuration for remote '"+self.remote_name +
                              "': '"+self.client_name+"' is not a MQTT connexion")
            raise CfgError(CfgError.BAD_VALUE, 'remote_control/protocol/name',
                           None, {'value': self.client_name}, self.logger)
        self.client: MQTTClient = client
        params: dict = self.config_protocol['params']
        missing: list = common.get_missing_mandatories(
            params,
            ['receive_topic', 'send_command_response_topic', 'send_scheduler_topic', 'send_devices_topic', 'send_device_states_base_topic'])
        if len(missing) > 0:
            raise CfgError(ECfgError.MISSING_NODES, '/remote_control/protocol/params', None, {'missing_children': missing}, self.logger)

        self.receive_topic = params['receive_topic']
        self.send_command_response_topic = params['send_command_response_topic']
        self.send_scheduler_topic = params['send_scheduler_topic']
        self.send_devices_topic = params['send_devices_topic']
        self.send_device_states_base_topic = params['send_device_states_base_topic']

    def get_name(self) -> str:
        return self.remote_name

    def get_client_name(self) -> str:
        return self.client_name

    def on_scheduler(self, scheduler_config: dict):
        data_json = json.dumps(scheduler_config, default=str)
        self.client.publish(data_json, self.send_scheduler_topic, retain=True)

    def on_devices(self, devices: dict[str, Device]):
        self.devices = devices
        self.__publish_devices()

    def __str2mqtt(string: str):
        return string.replace('+', '_').replace('#', '_').replace('$', '_')

    def __publish_devices(self):
        data_json = '['
        i = 0
        for device in self.devices.values():
            mqttid:str = MQTTRemoteClient.__str2mqtt(device.name)
            if i > 0:
                data_json = data_json + ','
            i += 1
            data_json = data_json + '{"name": "' + device.name + \
                '", "mqttid": "' + mqttid + '"}'
        data_json = data_json + ']'
        self.client.publish(data_json, self.send_devices_topic, retain=True)
        self.logger.debug(data_json)

    def on_client_connect(self):
        # subscribe to commands topic
        self.client.subscribe(self.receive_topic, 1)

        scheduler = self.callbacks.get_scheduler_config()
        data_json = json.dumps(scheduler, default=str, ensure_ascii=False)
        self.client.publish(data_json, self.send_scheduler_topic, retain=True)
        # self.logger.debug(data_json)

        # Subscribe to output topic :
        # We need to erase all previous published data for old devices may be still there
        # self.client.subscribe(data_json, self.send_devices_topic+'/#', 1)

        self.__publish_devices()

    def on_client_disconnect(self):
        pass

    def on_server_alive(self, is_alive: bool):
        pass

    def on_client_message(self, message):
        if isinstance(message, mqtt.MQTTMessage):
            try:
                # if message.topic.startswith(self.send_devices_topic+'/'):
                # See if this topic is for a known device or an old one
                if message.topic == self.receive_topic:
                    data = json.loads(message.payload)
                    command = data['command']
                    params = data['params']
                    if command == 'set_setpoint':
                        floatData = common.toFloat(
                            params['setpoint'], self.logger, "on_client_message(): Received invalid value on '"+message.topic+"' : ")
                        if floatData:
                            self.callbacks.set_device_parameter(
                                self.remote_name, params['device_name'], 'setpoint', floatData)
                    elif command == 'set_devices_order':
                        self.callbacks.set_devices_order(self.remote_name, params)
                    elif command == 'set_device_name':
                        self.callbacks.set_device_name(self.remote_name, params['old_name'], params['new_name'])
                    elif command == 'set_schedule':
                        self.callbacks.set_schedule(self.remote_name, params)
                    elif command == 'set_tempsets':
                        self.callbacks.set_temperature_sets(
                            self.remote_name, params['temperature_sets'], params['schedule_name'])
                    elif command == 'set_tempset_name':
                        self.callbacks.set_temperature_set_name(
                            self.remote_name, params['old_name'], params['new_name'], params['schedule_name'])
                    elif command == 'set_schedule_name':
                        self.callbacks.set_schedule_name(self.remote_name, params['old_name'], params['new_name'])
                    elif command == 'delete_schedule':
                        self.callbacks.delete_schedule(
                            self.remote_name, params['schedule_name'])
                    elif command == 'set_active_schedule':
                        self.callbacks.set_active_schedule(
                            self.remote_name, params['schedule_name'])
                    elif command == 'set_schedules_order':
                        self.callbacks.set_schedules_order(self.remote_name, params)
                    else:
                        err = CfgError(ECfgError.BAD_VALUE, message.topic, None, {'value':"'command':"+command}, self.logger)
                        self.on_server_response('failure', err.to_dict())
            except Exception as exc:
                self.logger.error("on_client_message(): Exception handling received data on topic '" +
                                  message.topic+"', data: '"+str(message.payload)+"'")
                #self.logger.error(str(exc))
                err = CfgError(ECfgError.EXCEPTION, message.topic, None, {'exception':str(exc)}, self.logger)
                self.on_server_response('failure', err.to_dict())

    def __send_device_status(self, device_name: str):
        device: Device = self.devices[device_name]
        mqttid:str = MQTTRemoteClient.__str2mqtt(device.name)
        topic = self.send_device_states_base_topic + '/' + mqttid
        data_json = json.dumps(
            {"current_temp": device.current_temperature,
             "setpoint": device.setpoint,
             "state": str(device.available).lower()
             }, default=str)
        self.client.publish(data_json, topic, retain=True, qos=1)

    def on_device_state(self, device_name: str, available: bool):
        self.__send_device_status(device_name)

    def on_device_current_temperature(self, device_name: str, value: float):
        self.__send_device_status(device_name)

    def on_device_setpoint(self, device_name: str, value: float):
        self.__send_device_status(device_name)

    def on_server_response(self, status: str, error: dict = None):
        topic = self.send_command_response_topic
        if error:
            data_json = json.dumps({'status': status, 'error': error}, default=str)
        else:
            data_json = json.dumps({'status': status}, default=str)
        self.client.publish(data_json, topic, retain=False, qos=1)
