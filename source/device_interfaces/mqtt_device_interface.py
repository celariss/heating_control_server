__author__ = "Jérôme Cuq"

from datetime import datetime, timedelta, timezone, tzinfo
import common
import logging
import device
from errors import *
from .device_interface_callbacks import DeviceInterfaceCallbacks
from .device_interface_base import DeviceInterfaceBase
from protocols.mqtt_protocol_handler import MQTTProtocolHandler
from device import Device
import re


class EDevTopic(Enum):
    """ Enumeration of device (and auto-discovery) parameters topics
        A topic value is the id of this device parameter in configuration
    """    
    device_base_topic = "device_base_topic"
    on_current_temp_subtopic = "on_current_temp_subtopic"
    on_setpoint_subtopic = "on_setpoint_subtopic"
    on_state_subtopic = "on_state_subtopic"
    on_min_temp_subtopic = "on_min_temp_subtopic"
    on_max_temp_subtopic = "on_max_temp_subtopic"
    set_setpoint_subtopic = "set_setpoint_subtopic"

class EAutoDiscoveryTopic(Enum):
    """ Enumeration of auto-discovery specific parameters topics
    """
    friendly_name_subtopic = 'friendly_name_subtopic'
    last_updated_subtopic = 'last_updated_subtopic'

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
        # will contain "partially" auto discovered devices,
        # we wait for friendly_name AND last_update messages before deciding if a device can be automatically added
        # note : dictionary key is the device entity name
        self.init_date = datetime.now(timezone(timedelta(0)))
        self.auto_discovered: dict[str, device.Device] = {}
        # list of devices declared in configuration file
        # dictionary key is device name
        self.devices: dict[str, device.Device] = devices
        # list of devices published by automation server
        # dictionary key is entity name
        self.available_devices: dict[str, device.Device] = {}
        self.auto_discovery: list[dict] = auto_discovery
        self.device_topic_re: re.Pattern = re.compile('([^/]+)/([^/]+)/?')

    def __check_auto_discovery(self, auto_discovery: list[dict]) -> CfgError:
        mandatories:list = [t.value for t in EDevTopic] + [t.value for t in EAutoDiscoveryTopic]
        for item in auto_discovery:
            missing: list = common.get_missing_mandatories(item, mandatories)
            if len(missing) > 0:
                return CfgError(ECfgError.MISSING_NODES, '/settings/auto_discovery', None, {'missing_children':missing}, self.logger)
            # We remove the trailing /, if present
            item[EDevTopic.device_base_topic.value] = item[EDevTopic.device_base_topic.value].rstrip('/')
            # We remove the starting /, if present
            self.__remove_parameter_starting_slash(item)
        return None

    def __check_devices(self, devices: dict[str, Device]) -> CfgError:
        mandatories:list = [t.value for t in EDevTopic]
        for device in devices.values():
            missing: list = common.get_missing_mandatories(device.protocol_params, mandatories)
            if len(missing) > 0:
                return CfgError(ECfgError.MISSING_NODES, '/devices/'+device.name+"/protocol[name='"+device.protocol_client_name+"']/params", None, {'missing_children':missing}, self.logger)
            # We remove the trailing /, if present
            device.protocol_params[EDevTopic.device_base_topic.value] = device.protocol_params[EDevTopic.device_base_topic.value].rstrip('/')
            # We remove the starting /, if present
            self.__remove_parameter_starting_slash(device.protocol_params)
        return None

    def __remove_parameter_starting_slash(self, map: dict):
        for item in map.keys():
            if item.endswith('_subtopic'):
                map[item] = map[item].lstrip('/')

    def set_device_parameter(self, device: device.Device, param_name:str, param_value):
        if param_name == 'setpoint':
            topic = self.__get_mqtt_topic(
                device.protocol_params, EDevTopic.set_setpoint_subtopic.value)
            if topic:
                self.logger.info("["+device.protocol_client_name+"]: Setting "+param_name +
                                 " for device['"+device.name+"'] with value '"+str(param_value)+"'")
                self.callbacks.send_message_to_device(
                    device, {'type': 'publish', 'topic': topic, 'payload': str(param_value)})
            else:
                self.logger.error("Missing topic '"+EDevTopic.set_setpoint_subtopic.value +
                                  "' in device '"+device.name+"' configuration")

    def on_devices(self, devices: dict[str, Device]):
        # We check the content of devices
        self.__check_devices(devices)
        self.__subscribe_to_devices(devices)

    def on_available_devices(self, devices: dict[str, Device]):
        # We check the content of devices
        self.__check_devices(devices)
        self.available_devices = devices

    def __subscribe_to_devices(self, new_devices: dict[str, Device] = None):
        current_subscriptions: dict[str, Device] = {}
        if new_devices:
            current_subscriptions = self.devices.copy()
            self.devices = new_devices

        for devname in self.devices:
            if devname in current_subscriptions:
                # We already subscribed for changes on this device
                current_subscriptions.pop(devname)
            else:
                # We need to subscribe for changes on this device
                device:Device = self.devices[devname]
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
        subtopics = [(EDevTopic.on_current_temp_subtopic.value,'current temperature'),
                     (EDevTopic.on_setpoint_subtopic.value, 'temperature setpoint'),
                     (EDevTopic.on_state_subtopic.value, 'state'), 
                     (EDevTopic.on_min_temp_subtopic.value, 'min temperature'),
                     (EDevTopic.on_max_temp_subtopic.value, 'max temperature')]
        for item in subtopics:
            topic = self.__get_mqtt_topic(device.protocol_params, item[0])
            name = item[1]
            if topic:
                self.logger.debug("["+device.protocol_client_name+"]: {operation} for device['" +
                              device.name+"'] "+name+" with topic '"+topic+"'")
                self.callbacks.send_message_to_device(device, {'type': operation, 'topic': topic})

    def __on_device_message(self, dev:Device, message, notify2callback:bool):
        topic_name = self.__get_topic_name(dev.protocol_params, message.topic)
        if topic_name==EDevTopic.on_current_temp_subtopic.value:
            floatData = common.toFloat(
                message.payload, self.logger, "on_client_message(): Received invalid data on '"+topic_name+"' : ")
            if floatData:
                dev.current_temperature = floatData
                if notify2callback:
                    self.callbacks.on_device_current_temperature(dev, floatData)
        
        elif topic_name==EDevTopic.on_setpoint_subtopic.value:
            floatData = common.toFloat(
                message.payload, self.logger, "on_client_message(): Received invalid data on '"+topic_name+"' : ")
            if floatData:
                prev:float = dev.setpoint
                dev.setpoint = floatData
                if notify2callback:
                    self.callbacks.on_device_setpoint(dev, prev)

        elif topic_name==EDevTopic.on_state_subtopic.value:
            state = MQTTDeviceInterface.__str_2_device_state(message.payload)
            if state == None:
                self.logger.warning(
                    "on_client_message(): Received invalid data on '"+topic_name+"' : "+message.payload)
            else:
                dev.available = state
                if notify2callback:
                    self.callbacks.on_device_state(dev, state)
        
        elif topic_name==EDevTopic.on_min_temp_subtopic.value:
            floatData = common.toFloat(
                message.payload, self.logger, "on_client_message(): Received invalid data on '"+topic_name+"' : ")
            if floatData:
                dev.min_temperature = floatData
                if notify2callback:
                    self.callbacks.on_device_min_temperature(dev, floatData)
                        
        elif topic_name==EDevTopic.on_max_temp_subtopic.value:
            floatData = common.toFloat(
                message.payload, self.logger, "on_client_message(): Received invalid data on '"+topic_name+"' : ")
            if floatData:
                dev.max_temperature = floatData
                if notify2callback:
                    self.callbacks.on_device_max_temperature(dev, floatData)
    
    def on_client_message(self, client_name: str, message):
        dev:Device

        for dev in self.devices.values():
            self.__on_device_message(dev, message, True)
        
        for dev in self.available_devices.values():
            self.__on_device_message(dev, message, False)

        if len(self.auto_discovery) > 0:
            # auto discovery is enabled
            for item in self.auto_discovery:
                base_topic = item[EDevTopic.device_base_topic.value] + '/'
                if message.topic.startswith(base_topic):
                    match: re.Match = self.device_topic_re.match(message.topic[len(base_topic):])
                    if match:
                        entity = match.group(1)
                        if not entity in self.available_devices:
                            command = match.group(2)
                            device: Device = None
                            if not entity in self.auto_discovered:
                                device = Device('', entity, self.protocol_type, client_name, {
                                    EDevTopic.device_base_topic.value: base_topic + entity,
                                    EDevTopic.on_current_temp_subtopic.value: item[EDevTopic.on_current_temp_subtopic.value],
                                    EDevTopic.on_setpoint_subtopic.value: item[EDevTopic.on_setpoint_subtopic.value],
                                    EDevTopic.on_state_subtopic.value: item[EDevTopic.on_state_subtopic.value],
                                    EDevTopic.on_min_temp_subtopic.value: item[EDevTopic.on_min_temp_subtopic.value],
                                    EDevTopic.on_max_temp_subtopic.value: item[EDevTopic.on_max_temp_subtopic.value],
                                    EDevTopic.set_setpoint_subtopic.value: item[EDevTopic.set_setpoint_subtopic.value]
                                })
                                self.auto_discovered[entity] = device
                            else:
                                device = self.auto_discovered[entity]
                            
                            self.__on_device_message(device, message, False)
                            if command == item[EAutoDiscoveryTopic.friendly_name_subtopic.value]:
                                device.name = str(message.payload).strip('"\'')               
                            elif command == item[EAutoDiscoveryTopic.last_updated_subtopic.value]:
                                device.last_updated = datetime.fromisoformat(str(message.payload))
                            # we add this device only if we have a name and a last_updated date recent enough
                            # or if it is a device present in configuration
                            if device.name != '' and device.last_updated > (self.init_date-timedelta(hours=5)):
                                self.callbacks.on_discovered_device(device)
                                #self.auto_discovered.pop(entity)

    # def __isknown_device(self, entity:str) -> bool:
    #     for name in self.devices:
    #         if self.devices[name].entity == entity:
    #             return True
    #     return False
    
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
                base_topic: str = item[EDevTopic.device_base_topic.value]
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
    def __get_mqtt_topic(self, mqtt_device_params, topic) -> str:
        if topic in mqtt_device_params:
            return mqtt_device_params[EDevTopic.device_base_topic.value]+'/'+mqtt_device_params[topic]
        return None

    def __get_topic_name(self, mqtt_device_params:dict, mqtt_topic:str) -> str:
        base_topic = mqtt_device_params[EDevTopic.device_base_topic.value]
        if mqtt_topic.startswith(base_topic+'/'):
            sub_topic = mqtt_topic[len(base_topic)+1:]
            for name in mqtt_device_params:
                if mqtt_device_params[name] == sub_topic:
                    return name
        return None
