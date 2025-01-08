__author__ = "Jérôme Cuq"

import copy
import datetime
import common
import json
import logging
import paho.mqtt.client as mqtt
from device import Device
from protocols.mqttclient import MQTTClient
from thread_base import ThreadBase
from .remote_client_base import RemoteClientBase
from .remote_control_callbacks import RemoteControlCallbacks
from errors import *


class MQTTRemoteClient(RemoteClientBase):
    def __init__(self, remote_name, config_remote_client, client: object, devices: dict[str, Device], available_devices: dict[str, Device], callbacks: RemoteControlCallbacks):
        self.logger = logging.getLogger('hcs.mqttremoteclient')
        self.config_remote_client = config_remote_client
        # list of devices declared in configuration file
        # dictionary key is device name
        self.devices: dict[str,Device] = copy.copy(devices)
        # list of devices published by automation server
        # dictionary key is entity name
        self.available_devices: dict[str,Device] = available_devices
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
            ['receive_topic', 'send_command_response_topic', 'send_scheduler_topic', 'send_devices_topic', \
             'send_entities_topic', 'send_device_states_base_topic', 'send_is_alive_topic', 'is_alive_period'])
        if len(missing) > 0:
            raise CfgError(ECfgError.MISSING_NODES, '/remote_control/protocol/params', None, {'missing_children': missing}, self.logger)

        self.receive_topic = params['receive_topic']
        self.send_command_response_topic = params['send_command_response_topic']
        self.send_scheduler_topic = params['send_scheduler_topic']
        self.send_devices_topic = params['send_devices_topic']
        self.send_entities_topic = params['send_entities_topic']
        self.send_device_states_base_topic = params['send_device_states_base_topic']
        self.send_is_alive_topic = params['send_is_alive_topic']

        self.is_alive_period = common.toInt(params['is_alive_period'], self.logger, default=-1)
        if self.is_alive_period == -1:
            raise CfgError(ECfgError.BAD_VALUE, '/remote_control/protocol/params', 'is_alive_period', {'value': params['is_alive_period']}, self.logger)
        self.is_alive_thread: ThreadBase = ThreadBase()

    def start(self):
        self.is_alive_thread.start(self.__is_alive_thread)

    def stop(self):
        self.is_alive_thread.stop()

    def get_name(self) -> str:
        return self.remote_name

    def get_client_name(self) -> str:
        return self.client_name

    def on_scheduler(self, scheduler_config: dict):
        data_json = json.dumps(scheduler_config, default=str)
        self.client.publish(data_json, self.send_scheduler_topic, retain=True)

    def on_devices(self, devices: dict[str, Device]):
        # Remove topic of devices that do not exist anymore
        for devname in self.devices:
            if not devname in devices:
                mqttid:str = MQTTRemoteClient.__str2mqtt(devname)
                self.__remove_device_topic(mqttid)
        # must publish data for new devices (current temp & setpoint)
        publish_list:list = []
        for devname in devices:
            if not devname in self.devices:
                publish_list.append(devname)
        # publish devices list
        self.devices = copy.copy(devices)
        self.__publish_devices()
        # and data for new ones
        for devname in publish_list:
            self.send_device_data(self.devices[devname])

    def on_available_devices(self, devices: dict[str, Device]):
        self.available_devices = devices
        self.__publish_available_devices()

    def __str2mqtt(string: str):
        return string.replace('+', '_').replace('#', '_').replace('$', '_')

    def __publish_devices(self):
        data_json = '['
        i = 0
        for device in self.devices.values():
            entity:str = device.entity
            mqttid:str = MQTTRemoteClient.__str2mqtt(device.name)
            if i > 0:
                data_json = data_json + ','
            i += 1
            data_json = data_json + '{"name": "' + device.name + \
                '", "mqttid": "' + mqttid + '", "srventity":"' + entity + '"}'
        data_json = data_json + ']'
        self.client.publish(data_json, self.send_devices_topic, retain=True)
        self.logger.debug(data_json)

    def __publish_available_devices(self):
        data_json = '['
        i = 0
        for device in self.available_devices.values():
            entity:str = device.entity
            if i > 0:
                data_json = data_json + ','
            i += 1
            data_json = data_json + '{"name": "' + device.name + \
                '", "srventity":"' + entity + '"}'
        data_json = data_json + ']'
        self.client.publish(data_json, self.send_entities_topic, retain=True)
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
        self.client.subscribe(self.send_device_states_base_topic+'/#', 1)

        self.__publish_devices()
        self.__publish_available_devices()

    def on_client_disconnect(self):
        pass

    def on_server_alive(self, is_alive: bool):
        self.logger.debug('on_server_alive()')
        topic = self.send_is_alive_topic
        if is_alive:
            data = datetime.datetime.now().isoformat()
        else:
            data = ''
        self.client.publish(data, topic, retain=True, qos=1)

    def on_client_message(self, message):
        if isinstance(message, mqtt.MQTTMessage):
            try:
                if message.topic.startswith(self.send_device_states_base_topic+'/'):
                    if message.payload != '':
                        # See if this topic is for a known device or an old one
                        mqttid = message.topic[len(self.send_device_states_base_topic)+1:]
                        found:bool = False
                        for device in self.devices.values():
                            devmqttid:str = MQTTRemoteClient.__str2mqtt(device.name)
                            if mqttid == devmqttid:
                                found = True
                                break
                        if not found:
                            self.__remove_device_topic(mqttid)

                elif message.topic == self.receive_topic:
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
                    elif command == 'add_device':
                        self.callbacks.add_device(self.remote_name, params['name'], params['srventity'])
                    elif command == 'set_device_entity':
                        self.callbacks.set_device_entity(self.remote_name, params['name'], params['new_srventity'])
                    elif command == 'delete_device':
                        self.callbacks.delete_device(self.remote_name, params['name'])
                    elif command == 'set_schedule':
                        self.callbacks.set_schedule(self.remote_name, params)
                    elif command == 'set_scheduler_settings':
                        self.callbacks.set_scheduler_settings(self.remote_name, params)
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

    def send_device_data(self, device:Device):
        #device: Device = self.devices[device.name]
        mqttid:str = MQTTRemoteClient.__str2mqtt(device.name)
        topic = self.__get_device_states_topic(mqttid)
        data_json = json.dumps(
            {"current_temp": device.current_temperature,
             "setpoint": device.setpoint,
             "state": str(device.available).lower(),
             "min_temp": device.min_temperature,
             "max_temp": device.max_temperature,
             }, default=str)
        self.client.publish(data_json, topic, retain=True, qos=1)

    def __remove_device_topic(self, mqttid:str):
        self.client.publish('', self.__get_device_states_topic(mqttid), retain=True, qos=1)
        self.logger.info("Removed old device topic : "+mqttid)

    def __get_device_states_topic(self, mqttid:str) -> str:
        return self.send_device_states_base_topic + '/' + mqttid

    def on_device_state(self, device:Device, available: bool):
        self.send_device_data(device)

    def on_device_current_temperature(self, device:Device, value: float):
        self.send_device_data(device)

    def on_device_min_temperature(self, device:Device, value:float):
        self.send_device_data(device)

    def on_device_max_temperature(self, device:Device, value:float):
        self.send_device_data(device)

    def on_device_setpoint(self, device:Device):
        self.send_device_data(device)

    def on_server_response(self, status: str, error: dict = None):
        topic = self.send_command_response_topic
        if error:
            data_json = json.dumps({'status': status, 'error': error}, default=str)
        else:
            data_json = json.dumps({'status': status}, default=str)
        self.client.publish(data_json, topic, retain=False, qos=1)

    # Thread that sends is alive ping
    def __is_alive_thread(self):
        self.logger.info('mqtt "server is alive" thread started')
        while self.is_alive_thread.wait(self.is_alive_period):
            self.on_server_alive(True)
        self.logger.info('mqtt "server is alive" thread has stopped')
