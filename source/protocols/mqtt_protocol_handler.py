__author__      = "Jérôme Cuq"

import logging
import random

from .protocol_handler_base import *
from .mqttclient import MQTTClient

class MQTTProtocolHandler(ProtocolHandlerBase):

    # Implementation of ProtocolHandlerBase class

    def __init__(self, clients_config: dict, callbacks: ProtocolHandlerCallbacks):
        self.logger: logging.Logger = logging.getLogger('hcs.mqtt')
        self.callbacks: ProtocolHandlerCallbacks = callbacks
        self.is_connected: bool = False
        self.mqttclients = {}
        self.mqtt_transport = 'websockets' # or 'tcp'
        self.mqtt_clientid = "HeatingControlServer-" + str(random.randint(10000,99999))
        self.ha_status_subscriptions:list = []
        for client_config in clients_config:
            name = client_config['name']
            mqtt_user = client_config['user']
            mqtt_pwd = client_config['pwd']
            mqtt_broker = client_config['broker']
            mqtt_port = client_config['port']
            mqtt_ssl = client_config['ssl']
            mqtt_cleansession = client_config['clean_session']
            mqtt_client = MQTTClient(self.mqtt_clientid, mqtt_broker, mqtt_port, mqtt_user, mqtt_pwd, self.mqtt_transport, userdata=name, clean_session=mqtt_cleansession, ssl=mqtt_ssl)
            mqtt_client.set_callbacks(on_connect=self.__on_connect, on_disconnect=self.__on_disconnect, on_message=self.__on_message)
            self.mqttclients[name] = (mqtt_client, client_config)

    def get_config_type() -> str:
        return 'mqtt'

    def get_client_from_name(self, client_name: str) -> object:
        client = self.mqttclients.get(client_name,None)
        if client:
            return client[0]
        return None

    def connect(self):
        for clientname in self.mqttclients:
            client = self.mqttclients[clientname][0]
            if not client.is_connected():
                self.logger.info("Interface '"+clientname+"' : connecting to mqtt broker:'" + client.broker + ":" + str(client.port) + ", 'user:'" + client.user + "'")
                client.connect()
        
    def disconnect(self):
        for clientname in self.mqttclients:
            client = self.mqttclients[clientname][0]
            if not client.is_connected():
                client.disconnect()
                self.ha_status_subscriptions = []
                self.logger.info("Interface '"+clientname+"' : disconnected")

    # protocol_params may be either:
    #    { 'type': 'publish', 'topic': str_value, 'payload': str_value, 'qos': int, 'retain': bool }
    # or { 'type': 'subscribe', 'topic': str_value, 'qos': int }
    # Note: 'retain' and 'qos' are optional
    def send_message(self, client_name: str, protocol_params:dict):
        if client_name in self.mqttclients:
            client_tuple = self.mqttclients[client_name]
            client: MQTTClient = client_tuple[0]
            if client.is_connected():
                if 'qos' in protocol_params: qos = protocol_params['qos']
                else: qos = 1
                if  protocol_params['type']=='publish':
                    self.logger.debug("Interface '"+client_name+"' : Publishing '"+str(protocol_params['payload'])+"' to '"+protocol_params['topic']+"'")
                    if 'retain' in protocol_params: retain = protocol_params['retain']
                    else: retain = False
                    client.publish(protocol_params['payload'], protocol_params['topic'], retain, qos=qos)
                elif protocol_params['type']=='subscribe':
                    self.__subscribe(client, client_name, protocol_params['topic'], qos)
            else:
                self.logger.debug("Interface '"+client_name+"' NOT CONNECTED : publish command ignored ('"+str(protocol_params['payload'])+"' on topic '"+protocol_params['topic']+"')")
    
    # END OF ProtocolHandlerBase implementation

    # Private methods
    def __subscribe(self, client:MQTTClient, client_name:str, topic:str, qos:int):
        self.logger.debug("Interface '"+client_name+"' : Subscribing to '"+topic+"'")
        client.subscribe(topic, qos=qos)

    def __get_mqttclient_name(self, mqtt_client) -> str:
        for item in self.mqttclients.items():
            if item[1][0] == mqtt_client:
                return item[0]
        return None

    def __on_message(self, client:MQTTClient, client_name:str, message, tmp=None):
        try:
            message.payload = message.payload.decode("utf-8")
        except UnicodeDecodeError:
            self.logger.error('Received invalid UTF-8 payload')
            pass

        # This message may be a server status change
        for item in self.ha_status_subscriptions:
            if client_name==item[0] and message.topic==item[1]:
                self.callbacks.on_server_alive_for_client(MQTTProtocolHandler.get_config_type(), client_name, message.payload=='online')
                return
        
        self.callbacks.on_protocol_message(MQTTProtocolHandler.get_config_type(), client_name, message)

    def __on_connect(self, client:MQTTClient, client_name:str, message, returncode):
        if returncode:
            self.logger.warning("["+client_name+"]: Not connected ! Return Code :" + str(returncode))
            self.callbacks.on_protocol_disconnect(MQTTProtocolHandler.get_config_type(), client_name)
            self.is_connected = False
        else:
            self.logger.info("["+client_name+"]: Connected !")
            self.callbacks.on_protocol_connect(MQTTProtocolHandler.get_config_type(), client_name)
            self.is_connected = True
            # We need to get HA status to change devices availability to False if HA goes offline
            if client_name in self.mqttclients:
                client_tuple = self.mqttclients[client_name]
                client: MQTTClient = client_tuple[0]
                if 'on_ha_status_topic' in client_tuple[1]:
                    topic = client_tuple[1]['on_ha_status_topic']
                    self.__subscribe(client, client_name, topic, 1)
                    self.ha_status_subscriptions.append((client_name,topic))

    def __on_disconnect(self, client:MQTTClient, client_name:str, returncode):
        self.logger.info("["+client_name+"]: Disconnected with code: "+str(returncode))
        self.is_connected = False
        self.ha_status_subscriptions = []
        self.callbacks.on_protocol_disconnect(MQTTProtocolHandler.get_config_type(), client_name)
