__author__      = "Jérôme Cuq"

from .remote_control_callbacks import RemoteControlCallbacks
from .remote_client_base import RemoteClientBase
from protocols.mqttclient import MQTTClient
from device import Device
from configuration import Configuration
import paho.mqtt.client as mqtt
import re
import logging
import json
import common

DEVNAME_VAR     = '$(devname)'
DEVNAME_VAR_ESC =  r'\$\(devname\)'

class MQTTRemoteClient(RemoteClientBase):
    def __init__(self, remote_name, config_remote_client, client:MQTTClient, callbacks:RemoteControlCallbacks):
        self.logger = logging.getLogger('hcs.mqttremoteclient')
        self.config_remote_client = config_remote_client
        self.callbacks = callbacks
        self.remote_name = remote_name
        self.config_protocol = config_remote_client['protocol']
        self.re:re.Pattern = re.compile('[\\w_@.-/]*'+DEVNAME_VAR_ESC+'[\\w_@.-/]*')
        self.client = client
        self.client_name = self.config_protocol['name']

        self.send_scheduler_topic = self.config_protocol['params']['send_scheduler_topic']
        self.send_devices_topic = self.config_protocol['params']['send_devices_topic']
        self.send_state_topic = self.config_protocol['params']['send_state_topic']
        self.send_current_temp_topic = self.config_protocol['params']['send_current_temp_topic']
        self.send_setpoint_topic = self.config_protocol['params']['send_setpoint_topic']
        self.send_command_response_topic = self.config_protocol['params']['send_command_response_topic']
        self.receive_setpoint_topic = self.config_protocol['params']['receive_setpoint_topic']
        self.receive_schedule_topic = self.config_protocol['params']['receive_schedule_topic']
        self.receive_tempsets_topic = self.config_protocol['params']['receive_tempsets_topic']
        self.receive_tempset_name_topic = self.config_protocol['params']['receive_tempset_name_topic']
        self.receive_schedule_name_topic = self.config_protocol['params']['receive_schedule_name_topic']
        self.receive_delete_schedule_topic = self.config_protocol['params']['receive_delete_schedule_topic']
        self.receive_active_schedule_topic = self.config_protocol['params']['receive_active_schedule_topic']
        self.receive_schedules_order_topic = self.config_protocol['params']['receive_schedules_order']
        
    def get_name(self)  -> str:
        return self.remote_name

    def get_client_name(self) -> str:
        return self.client_name

    def on_scheduler(self, scheduler_config:dict):
        data_json = json.dumps(scheduler_config, default=str)
        self.client.publish(data_json, self.send_scheduler_topic, retain=True)

    def on_client_connect(self):
        self.client.subscribe(self.receive_setpoint_topic, 1)
        self.client.subscribe(self.receive_schedule_topic, 1)
        self.client.subscribe(self.receive_tempsets_topic, 1)
        self.client.subscribe(self.receive_tempset_name_topic, 1)
        self.client.subscribe(self.receive_schedule_name_topic, 1)
        self.client.subscribe(self.receive_delete_schedule_topic, 1)
        self.client.subscribe(self.receive_active_schedule_topic, 1)
        self.client.subscribe(self.receive_schedules_order_topic, 1)

        scheduler = self.callbacks.get_scheduler_config()
        data_json = json.dumps(scheduler, default=str, ensure_ascii=False)
        self.client.publish(data_json, self.send_scheduler_topic, retain=True)
        #self.logger.debug(data_json)
        
        devices: dict[str,Device] = self.callbacks.get_devices()
        data_json = '['
        i = 0
        for device in devices.values():
            if i>0: data_json = data_json + ','
            i+=1
            data_json = data_json + '{"name": "' + device.name + '"}'
        data_json = data_json + ']'
        self.client.publish(data_json, self.send_devices_topic, retain=True)
        self.logger.debug(data_json)

    def on_client_disconnect(self):
        pass

    def on_server_alive(self, is_alive:bool):
        pass

    def on_client_message(self, message):
        if isinstance(message, mqtt.MQTTMessage):
            """ match:re.Match = self.re.match(message.topic)
            if match:
                m1 = match.group(0)
                m2 = match.group(1) """
            try:
                if message.topic == self.receive_setpoint_topic:
                    data = json.loads(message.payload)
                    floatData = common.toFloat(data['setpoint'], self.logger, "on_client_message(): Received invalid value on '"+message.topic+"' : ")
                    if floatData:
                        self.callbacks.set_device_parameter(self.remote_name, data['device_name'], 'setpoint', floatData)
                elif message.topic == self.receive_schedule_topic:
                    data = json.loads(message.payload)
                    self.callbacks.set_schedule(self.remote_name, data)
                elif message.topic == self.receive_tempsets_topic:
                    data = json.loads(message.payload)
                    self.callbacks.set_temperature_sets(self.remote_name, data['temperature_sets'], data['schedule_name'])
                elif message.topic == self.receive_tempset_name_topic:
                    data = json.loads(message.payload)
                    self.callbacks.set_temperature_set_name(self.remote_name, data['old_name'], data['new_name'], data['schedule_name'])
                elif message.topic == self.receive_schedule_name_topic:
                    data = json.loads(message.payload)
                    self.callbacks.set_schedule_name(self.remote_name, data['old_name'], data['new_name'])
                elif message.topic == self.receive_delete_schedule_topic:
                    data = json.loads(message.payload)
                    self.callbacks.delete_schedule(self.remote_name, data['schedule_name'])
                elif message.topic == self.receive_active_schedule_topic:
                    data = json.loads(message.payload)
                    self.callbacks.set_active_schedule(self.remote_name, data['schedule_name'])
                elif message.topic == self.receive_schedules_order_topic:
                    data = json.loads(message.payload)
                    self.callbacks.set_schedules_order(self.remote_name, data)
            except Exception as exc:
                self.logger.error("on_client_message(): Exception handling received data on topic '"+message.topic+"', data: '"+str(message.payload)+"'")
                self.logger.error(str(exc))

    def on_device_state(self, device_name:str, available:bool):
        topic = self.send_state_topic.replace(DEVNAME_VAR,device_name)
        self.client.publish(str(available).lower(), topic, retain=True, qos=1)

    def on_device_current_temperature(self, device_name:str, value:float):
        topic = self.send_current_temp_topic.replace(DEVNAME_VAR,device_name)
        self.client.publish(value, topic, retain=True, qos=1)

    def on_device_setpoint(self, device_name:str, value:float):
        topic = self.send_setpoint_topic.replace(DEVNAME_VAR,device_name)
        self.client.publish(value, topic, retain=True, qos=1)

    def on_server_response(self, status:str, error:dict=None):
        topic = self.send_command_response_topic
        if error:
            data_json = json.dumps({'status':status, 'error':error}, default=str)
        else:
            data_json = json.dumps({'status':status}, default=str)
        self.client.publish(data_json, topic, retain=False, qos=1)
