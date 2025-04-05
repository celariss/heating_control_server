__author__      = "Jérôme Cuq"

"""This file implements a simple mqqt client using eclipse paho mqtt library
    see :
    - example : https://cedalo.com/blog/configuring-paho-mqtt-python-client-with-examples/
    - topics : http://www.steves-internet-guide.com/understanding-mqtt-topics/
    - QoS : https://www.hivemq.com/blog/mqtt-essentials-part-6-mqtt-quality-of-service-levels/
         https://cedalo.com/blog/understanding-mqtt-qos/
"""

import paho.mqtt.client as mqtt
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes

from thread_base import ThreadBase

class MQTTClient:
    # If userdata is not provided (None), it will be set to current instance of MQTTClient on any callback calling
    def __init__(self, clientid, broker, port, user, pwd, transport = "websockets", userdata = None, clean_session=True, ssl = True):
        self.clientid = clientid
        self.user = user
        self.pwd = pwd
        self.version = '3'
        self.transport = transport
        self.broker = broker
        self.port = port
        self.protocol = None
        self.paho_client:mqtt.Client = None
        self.ssl = ssl
        if userdata:
            self.userdata = userdata
        else:
            self.userdata = self
        if self.version == '5':
            self.protocol = mqtt.MQTTv5
        if self.version == '3':
            self.protocol = mqtt.MQTTv311
        if self.protocol:
            self.paho_client = mqtt.Client(
                client_id=self.clientid,
                transport=self.transport,
                protocol=self.protocol,
                clean_session=clean_session,
                userdata=self.userdata,
                reconnect_on_failure=True)
        self.connect_thread: ThreadBase = ThreadBase()

    def delete(self):
        self.disconnect()

    # Callbacks must have following prototype :  
    # (MQTT v3) on_connect(paho_client, userdata, message, returncode)
    # (MQTT v5) TBD
    # on_disconnect(paho_client, userdata, returncode)
    # on_subscribe(self, paho_client, userdata, mid, granted_qos)
    # on_message(paho_client, userdata, message, tmp)
    # on_publish(paho_client, userdata, returncode)
    def set_callbacks(self, on_connect=None, on_disconnect=None, on_subscribe=None, on_message=None, on_publish=None):
        self.paho_client.on_connect = on_connect
        self.paho_client.on_disconnect = on_disconnect
        self.paho_client.on_subscribe = on_subscribe
        self.paho_client.on_message = on_message
        self.paho_client.on_publish = on_publish

    def connect(self):
        self.connect_thread.start(self.__connect_thread)

    def disconnect(self):
        self.connect_thread.stop()
        self.paho_client.loop_stop()
        self.paho_client.disconnect()

    def is_connected(self):
        return self.paho_client.is_connected()

    def subscribe(self, topic, qos=1):
        self.paho_client.subscribe(topic, qos)

    def unsubscribe(self, topic, qos=1):
        self.paho_client.unsubscribe(topic)

    def publish(self, data, topic:str, retain:bool=False, qos=1) -> bool:
        properties:Properties=Properties(PacketTypes.PUBLISH)
        properties.MessageExpiryInterval=30 # in seconds
        sendData = data
        if isinstance(data,str):
            sendData = bytearray(data, encoding="utf-8")
        mi: mqtt.MQTTMessageInfo = self.paho_client.publish(topic, sendData, retain=retain, qos=qos, properties=properties)
        return mi.rc == mqtt.MQTT_ERR_SUCCESS

    def __connect_thread(self):
        self.paho_client.username_pw_set(self.user, self.pwd)
        # code for tls secured connection
        if self.ssl:
            self.paho_client.tls_set(certfile=None, keyfile=None)

        isAlive:bool = True
        while isAlive:
            if not self.is_connected():
                try:
                    if self.version == '5':
                        properties:Properties=Properties(PacketTypes.CONNECT)
                        properties.SessionExpiryInterval=30*60 # in seconds
                        self.paho_client.connect(self.broker,
                                    port=self.port,
                                    clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
                                    properties=properties,
                                    keepalive=60)
                    if self.version == '3':
                        self.paho_client.connect(self.broker,port=self.port,keepalive=60)
                    
                    self.paho_client.loop_start()
                    return
                
                except TimeoutError:
                    # Need to try again
                    pass
                except Exception as exc:
                    pass
            isAlive = self.connect_thread.wait(5)