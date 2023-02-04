__author__      = "Jérôme Cuq"

from .device_interface_base import DeviceInterfaceBase
from .device_interface_callbacks import DeviceInterfaceCallbacks
import device
import logging
import common


class MQTTDeviceInterface(DeviceInterfaceBase):
    
    # Implementation of DeviceInterfaceBase class
    
    def __init__(self, callbacks:DeviceInterfaceCallbacks, ):
        self.logger = logging.getLogger('hcs.mqttdev')
        self.callbacks: DeviceInterfaceCallbacks = callbacks

    def set_device_parameter(self, device: device.Device, param_name, param_value):
        if param_name == 'setpoint':
            topic = self.__get_mqtt_topic(device.protocol_params, 'set_setpoint_topic')
            if topic:
                self.logger.info("["+device.protocol_client_name+"]: Setting "+param_name+" for device['"+device.name+"'] with value '"+str(param_value)+"'")
                self.callbacks.send_message_to_device(device, {'type': 'publish', 'topic': topic, 'payload':str(param_value)})
            else:
                self.logger.error("Missing topic '"+'set_setpoint_topic'+"' in device '"+device.name+"' configuration")

    def on_client_message(self, client_name: str, message):
        devices = self.callbacks.get_devices()
        for devname in devices:
            dev: device.Device = devices[devname]
            if dev.protocol_client_name == client_name:
                topic = self.__get_mqtt_topic(dev.protocol_params, 'on_current_temp_topic')
                if topic==message.topic:
                    floatData = common.toFloat(message.payload, self.logger, "on_client_message(): Received invalid data on '"+topic+"' : ")
                    if floatData:
                        self.callbacks.on_device_current_temperature(dev, floatData)
                else:
                    topic = self.__get_mqtt_topic(dev.protocol_params, 'on_setpoint_topic')
                    if topic==message.topic:
                        floatData = common.toFloat(message.payload, self.logger, "on_client_message(): Received invalid data on '"+topic+"' : ")
                        if floatData:
                            self.callbacks.on_device_setpoint(dev, floatData)
                    else:
                        topic = self.__get_mqtt_topic(dev.protocol_params, 'on_state_topic')
                        if topic==message.topic:
                            state = MQTTDeviceInterface.__str_2_device_state(message.payload)
                            if state==None: self.logger.warning("on_client_message(): Received invalid data on '"+topic+"' : "+message.payload)
                            else:
                                self.callbacks.on_device_state(dev, state)
    
    def on_server_alive_for_client(self, client_name: str, is_alive:bool):
        # We need to get HA status to change devices availability to False if HA goes offline
        if is_alive==False:
            self.__on_not_available(client_name)

    def on_server_alive(self, is_alive:bool):
        # We need to get HA status to change devices availability to False if HA goes offline
        if is_alive==False:
            self.__on_not_available()

    def __str_2_device_state(data:str) -> bool:
        if data=='unavailable': return False
        return True

    def on_client_connect(self, client_name: str):
        devices:dict[str, device.Device] = self.callbacks.get_devices()
        for devname in devices:
            device: device.Device = devices[devname]
            # Now we subscribe for changes
            topic = self.__get_mqtt_topic(device.protocol_params, 'on_current_temp_topic')
            if topic:
                self.logger.debug("["+client_name+"]: Subscribing for device['"+devname+"'] current temperature with topic '"+topic+"'")
                self.callbacks.send_message_to_device(device, {'type': 'subscribe', 'topic': topic})
            topic = self.__get_mqtt_topic(device.protocol_params, 'on_setpoint_topic')
            if topic: 
                self.logger.debug("["+client_name+"]: Subscribing for device['"+devname+"'] temperature setpoint with topic '"+topic+"'")
                self.callbacks.send_message_to_device(device, {'type': 'subscribe', 'topic': topic})
            topic = self.__get_mqtt_topic(device.protocol_params, 'on_state_topic')
            if topic:
                self.logger.debug("["+client_name+"]: Subscribing for device['"+devname+"'] state with topic '"+topic+"'")
                self.callbacks.send_message_to_device(device, {'type': 'subscribe', 'topic': topic})

    def on_client_disconnect(self, client_name: str):
        # We need to get HA status to change devices availability to False if HA goes offline
        self.__on_not_available(client_name)

    def __on_not_available(self, client_name:str = None):
        devices = self.callbacks.get_devices()
        for devname in devices:
            dev: device.Device = devices[devname]
            if (client_name==None or dev.protocol_client_name == client_name) and dev.available:
                # This device is no longer available
                self.callbacks.on_device_state(dev, False)

    # END OF DeviceInterfaceBase implementation
    
    # Private methods
    def __get_mqtt_topic(self, mqtt_device_params, topic):
        if topic in mqtt_device_params:
            return mqtt_device_params[topic]
        return None