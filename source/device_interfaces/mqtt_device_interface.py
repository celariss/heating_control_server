__author__ = "Jérôme Cuq"

import common
import logging
import device
from errors import *
from .device_interface_callbacks import DeviceInterfaceCallbacks
from .device_interface_base import DeviceInterfaceBase
from protocols.mqtt_protocol_handler import MQTTProtocolHandler
from device import Device
import re


class MQTTDeviceInterface(DeviceInterfaceBase):
    # Implementation of DeviceInterfaceBase class

    def __init__(self, devices: dict[str, Device], auto_discovery: list[dict], callbacks: DeviceInterfaceCallbacks):
        self.logger = logging.getLogger('hcs.mqttdev')
        self.protocol_type = MQTTProtocolHandler.get_config_type()
        self.callbacks: DeviceInterfaceCallbacks = callbacks
        # We check the content of auto_discovery
        err:CfgError = self.__check_auto_discovery(auto_discovery)
        if err: raise err
        # We check the content of devices
        err:CfgError = self.__check_devices(devices)
        if err: raise err
        self.devices: dict[str, device.Device] = devices
        self.auto_discovery: list[dict] = auto_discovery
        self.device_topic_re: re.Pattern = re.compile(
            '([^/]+)/([^/]+)/?')

    def __check_auto_discovery(self, auto_discovery: list[dict]) -> CfgError:
        for item in auto_discovery:
            missing: list = common.get_missing_mandatories(
                item,
                ['devices_base_topic', 'friendly_name_subtopic', 'on_current_temp_subtopic', 'on_setpoint_subtopic', 
                 'on_state_subtopic', 'on_min_temp_subtopic', 'on_max_temp_subtopic', 'set_setpoint_subtopic'])
            if len(missing) > 0:
                return CfgError(ECfgError.MISSING_NODES, '/settings/auto_discovery', None, {'missing_children':missing}, self.logger)
            # We remove the trailing /, if present
            item['devices_base_topic'] = item['devices_base_topic'].rstrip('/')
            # We remove the starting /, if present
            self.__remove_parameter_starting_slash(item)
        return None

    def __check_devices(self, devices: dict[str, Device]) -> CfgError:
        for device in devices.values():
            missing: list = common.get_missing_mandatories(device.protocol_params, [
                                                           'device_base_topic', 'on_current_temp_subtopic', 'on_setpoint_subtopic',
                                                           'on_state_subtopic', 'on_min_temp_subtopic', 'on_max_temp_subtopic', 'set_setpoint_subtopic'])
            if len(missing) > 0:
                return CfgError(ECfgError.MISSING_NODES, '/devices/'+device.name+"/protocol[name='"+device.protocol_client_name+"']/params", None, {'missing_children':missing}, self.logger)
            # We remove the trailing /, if present
            device.protocol_params['device_base_topic'] = device.protocol_params['device_base_topic'].rstrip(
                '/')
            # We remove the starting /, if present
            self.__remove_parameter_starting_slash(device.protocol_params)
        return None

    def __remove_parameter_starting_slash(self, map: dict):
        for item in map.keys():
            if item.endswith('_subtopic'):
                map[item] = map[item].lstrip('/')

    def set_device_parameter(self, device: device.Device, param_name, param_value):
        if param_name == 'setpoint':
            topic = self.__get_mqtt_topic(
                device.protocol_params, 'set_setpoint_subtopic')
            if topic:
                self.logger.info("["+device.protocol_client_name+"]: Setting "+param_name +
                                 " for device['"+device.name+"'] with value '"+str(param_value)+"'")
                self.callbacks.send_message_to_device(
                    device, {'type': 'publish', 'topic': topic, 'payload': str(param_value)})
            else:
                self.logger.error("Missing topic '"+'set_setpoint_subtopic' +
                                  "' in device '"+device.name+"' configuration")

    def on_devices(self, devices: dict[str, Device]):
        # We check the content of devices
        self.__check_devices(devices)
        self.__subscribe_to_devices(devices)

    def __subscribe_to_devices(self, new_devices: dict[str, device.Device] = None):
        current_subscriptions: dict[str, device.Device] = {}
        if new_devices:
            current_subscriptions = self.devices.copy()
            self.devices = new_devices

        for devname in self.devices:
            if devname in current_subscriptions:
                # We already subscribed for changes on this device
                current_subscriptions.pop(devname)
            else:
                # We need to subscribe for changes on this device
                device: Device = self.devices[devname]
                self.__subscribe(device)

        # Every device name left in current_subscriptions must be unsubcribed
        for device in current_subscriptions.values():
            # We need to unsubscribe for changes on this device
            self.__subscribe(device, 'unsubscribe')

    def __subscribe(self, device: device.Device, operation='subscribe'):
        """Subscribe or unsubscribe topics for given device

        :param device: device to (un)subscribe to
        :type device: device.Device
        :param operation: one of ['subscribe', 'unsubscribe'], defaults to 'subscribe'
        :type operation: str, optional
        """
        subtopics = [('on_current_temp_subtopic','current temperature'),
                     ('on_setpoint_subtopic', 'temperature setpoint'),
                     ('on_state_subtopic', 'state'), 
                     ('on_min_temp_subtopic', 'min temperature'),
                     ('on_max_temp_subtopic', 'max temperature')]
        for item in subtopics:
            topic = self.__get_mqtt_topic(device.protocol_params, item[0])
            name = item[1]
            if topic:
                self.logger.debug("["+device.protocol_client_name+"]: {operation} for device['" +
                              device.name+"'] "+name+" with topic '"+topic+"'")
                self.callbacks.send_message_to_device(device, {'type': operation, 'topic': topic})

    def on_client_message(self, client_name: str, message):
        is_known_device: bool = False
        for dev in self.devices.values():
            if message.topic.startswith(dev.protocol_params['device_base_topic']):
                is_known_device = True
            if dev.protocol_client_name == client_name:
                topic = self.__get_mqtt_topic(
                    dev.protocol_params, 'on_current_temp_subtopic')
                if topic == message.topic:
                    is_known_topic = True
                    floatData = common.toFloat(
                        message.payload, self.logger, "on_client_message(): Received invalid data on '"+topic+"' : ")
                    if floatData:
                        self.callbacks.on_device_current_temperature(
                            dev, floatData)
                else:
                    topic = self.__get_mqtt_topic(
                        dev.protocol_params, 'on_setpoint_subtopic')
                    if topic == message.topic:
                        is_known_topic = True
                        floatData = common.toFloat(
                            message.payload, self.logger, "on_client_message(): Received invalid data on '"+topic+"' : ")
                        if floatData:
                            self.callbacks.on_device_setpoint(dev, floatData)
                    else:
                        topic = self.__get_mqtt_topic(dev.protocol_params, 'on_state_subtopic')
                        if topic == message.topic:
                            is_known_topic = True
                            state = MQTTDeviceInterface.__str_2_device_state(
                                message.payload)
                            if state == None:
                                self.logger.warning(
                                    "on_client_message(): Received invalid data on '"+topic+"' : "+message.payload)
                            else:
                                self.callbacks.on_device_state(dev, state)
                        else:
                            topic = self.__get_mqtt_topic(dev.protocol_params, 'on_min_temp_subtopic')
                            if topic == message.topic:
                                is_known_topic = True
                                floatData = common.toFloat(
                                    message.payload, self.logger, "on_client_message(): Received invalid data on '"+topic+"' : ")
                                if floatData:
                                    self.callbacks.on_device_min_temperature(dev, floatData)
                            else:
                                topic = self.__get_mqtt_topic(dev.protocol_params, 'on_max_temp_subtopic')
                                if topic == message.topic:
                                    is_known_topic = True
                                    floatData = common.toFloat(
                                        message.payload, self.logger, "on_client_message(): Received invalid data on '"+topic+"' : ")
                                    if floatData:
                                        self.callbacks.on_device_max_temperature(dev, floatData)

        if is_known_device == False and len(self.auto_discovery) > 0:
            # auto discovery is enabled
            for item in self.auto_discovery:
                base_topic = item['devices_base_topic'] + '/'
                if message.topic.startswith(base_topic):
                    match: re.Match = self.device_topic_re.match(
                        message.topic[len(base_topic):])
                    if match:
                        entity = match.group(1)
                        command = match.group(2)
                        if command == item['friendly_name_subtopic']:
                            device: Device = Device(str(message.payload).strip('"\''), self.protocol_type, client_name, {
                                "device_base_topic": base_topic + entity,
                                "on_current_temp_subtopic": item['on_current_temp_subtopic'],
                                "on_setpoint_subtopic": item['on_setpoint_subtopic'],
                                "on_state_subtopic": item['on_state_subtopic'],
                                "on_min_temp_subtopic": item['on_min_temp_subtopic'],
                                "on_max_temp_subtopic": item['on_max_temp_subtopic'],
                                "set_setpoint_subtopic": item['set_setpoint_subtopic']
                            })
                            self.callbacks.on_discovered_device(device)

    def on_server_alive_for_client(self, client_name: str, is_alive: bool):
        # We need to get HA status to change devices availability to False if HA goes offline
        if is_alive == False:
            self.__on_not_available(client_name)

    def on_server_alive(self, is_alive: bool):
        # We need to get HA status to change devices availability to False if HA goes offline
        if is_alive == False:
            self.__on_not_available()

    def __str_2_device_state(data: str) -> bool:
        if data == 'unavailable':
            return False
        return True

    def on_client_connect(self, client_name: str):
        if len(self.auto_discovery) > 0:
            # auto discovery is enabled
            for item in self.auto_discovery:
                base_topic: str = item['devices_base_topic']
                if not base_topic.endswith('/'):
                    base_topic = base_topic + '/#'
                else:
                    base_topic = base_topic + '#'
                self.logger.debug(
                    "["+client_name+"]: Subscribing for device auto-discovery on topic '"+base_topic+"'")
                self.callbacks.send_message_to_client(self.protocol_type, client_name, {
                                                      'type': 'subscribe', 'topic': base_topic})
        self.__subscribe_to_devices()

    def on_client_disconnect(self, client_name: str):
        # We need to get HA status to change devices availability to False if HA goes offline
        self.__on_not_available(client_name)

    def __on_not_available(self, client_name: str = None):
        for dev in self.devices.values():
            if (client_name == None or dev.protocol_client_name == client_name) and dev.available:
                # This device is no longer available
                self.callbacks.on_device_state(dev, False)

    # END OF DeviceInterfaceBase implementation

    # Private methods
    def __get_mqtt_topic(self, mqtt_device_params, topic):
        if topic in mqtt_device_params:
            return mqtt_device_params['device_base_topic']+'/'+mqtt_device_params[topic]
        return None
