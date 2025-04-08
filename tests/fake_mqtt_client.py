import datetime
import json
import paho.mqtt.client as mqtt

class save_class:
    pass


class FakeMQTTClient:
    # static methods
    def replace_methods(target_class:type):
        FakeMQTTClient.change_methods(save_class, target_class)
        FakeMQTTClient.change_methods(target_class, FakeMQTTClient)

    def restore_methods(target_class:type):
        FakeMQTTClient.change_methods(target_class, save_class)

    def change_methods(target_class:type, source_class:type):
        target_class.__init__ = source_class.__init__
        target_class.delete = source_class.delete
        target_class.set_callbacks = source_class.set_callbacks
        target_class.connect = source_class.connect
        target_class.disconnect = source_class.disconnect
        target_class.is_connected = source_class.is_connected
        target_class.subscribe = source_class.subscribe
        target_class.unsubscribe = source_class.unsubscribe
        target_class.publish = source_class.publish

    def send_fake_message(cmdname:str, params:dict, topic:str):
        msg = '{ "command": "'+cmdname+'", "params": '+json.dumps(params, default=str)+' }'
        FakeMQTTClient.send_fake_message_raw(msg, topic)

    def send_fake_message_raw(msg:str, topic:str, encode:bool=True):
        if FakeMQTTClient.instance.on_message:
            message:mqtt.MQTTMessage = mqtt.MQTTMessage()
            if encode:
                message.payload = msg.encode("utf-8")
                message.topic = topic.encode("utf-8")
            else:
                message.payload = msg
                message.topic = topic
            FakeMQTTClient.instance.on_message(FakeMQTTClient.instance, FakeMQTTClient.instance.userdata, message)

    instance = None

    def __init__(self, clientid, broker, port, user, pwd, transport = "websockets", userdata = None, clean_session=True, ssl = True):
        self.clientid = clientid
        self.user = user
        self.pwd = pwd
        self.transport = transport
        self.broker = broker
        self.port = port
        self.ssl = ssl
        if userdata:
            self.userdata = userdata
        else:
            self.userdata = self
        self.bconnected = False
        self.published_messages = {}
        self.deleted = False
        FakeMQTTClient.instance = self

    def delete(self):
        self.disconnect()
        self.deleted = True

    def set_callbacks(self, on_connect=None, on_disconnect=None, on_subscribe=None, on_message=None, on_publish=None):
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.on_subscribe = on_subscribe
        self.on_message = on_message
        self.on_publish = on_publish

    def connect(self):
        self.bconnected = True
        self.on_connect(self, self.userdata, "", None)

    def disconnect(self):
        self.bconnected = False
        self.on_disconnect(self, self.userdata, None)

    def is_connected(self):
        return self.bconnected

    def subscribe(self, topic, qos=1):
        pass

    def unsubscribe(self, topic, qos=1):
        pass

    def publish(self, data, topic:str, retain:bool=False, qos=1) -> bool:
        self.published_messages[topic] = data
        return True