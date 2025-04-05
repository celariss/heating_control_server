import logging
from .mqtt_protocol_handler import MQTTProtocolHandler
from .protocol_handler_base import ProtocolHandlerBase
from .protocol_handler_callbacks import ProtocolHandlerCallbacks
from .mqttclient import MQTTClient

# This class manages all the protocol clients declared in the configuration file.
# It instanciate one protocol handler for each protocol type.
# Each protocol handler instanciate one connexion client per name declared in confguration file.
class Protocols:
    def __init__(self, config_protocols, callbacks: ProtocolHandlerCallbacks):
        self.config_protocols: dict = config_protocols
        self.logger: logging.Logger = logging.getLogger('hcs.protocols')
        self.protocol_handlers: dict = {}
        # Only MQTT protocol is known so far
        MQTT = MQTTProtocolHandler.get_config_type()
        if MQTT in config_protocols:
            self.protocol_handlers[MQTT] = MQTTProtocolHandler(config_protocols[MQTT], callbacks)

    def stop(self):
        for handler in self.protocol_handlers.values():
            handler.stop()

    def getProtocolTypes(self) -> list[str]:
        return self.protocol_handlers.keys()

    # Find, in all protocol handlers, the instance of the connexion client from given name
    def get_client_by_name(self, client_name: str) -> object:
        for handler in self.protocol_handlers.values():
            client = handler.get_client_from_name(client_name)
            if client:
                return client
        return None

    def get_protocol_type_from_name(self, client_name: str) -> str:
        for prot_type in self.protocol_handlers:
            client = self.protocol_handlers[prot_type].get_client_from_name(client_name)
            if client:
                return prot_type
        return None

    def connect(self):
        for handler in self.protocol_handlers.values():
            handler.connect()

    def disconnect(self):
        for handler in self.protocol_handlers.values():
            handler.disconnect()

    def is_connected(self, protocol_type, client_name):
        client = self.protocol_handlers[protocol_type].get_client_from_name(client_name)
        if client:
            return client.is_connected()
        return False

    def are_all_connected(self):
        for handler in self.protocol_handlers.values():
            if not handler.is_connected():
                return False
        return True

    # protocol_params content depends on the protocol handler implementation
    def send_message(self, protocol_type: str, client_name: str, protocol_msg_params:dict):
        handler: ProtocolHandlerBase = self.protocol_handlers.get(protocol_type, None)
        if handler:
            handler.send_message(client_name, protocol_msg_params)