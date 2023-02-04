from .mqttclient import MQTTClient

class ProtocolHandlerCallbacks:
    # message content and type depend on protocol_type
    def on_protocol_message(self, protocol_type: str, client_name: str, message):
        pass

    def on_protocol_connect(self, protocol_type: str, client_name: str):
        pass

    def on_protocol_disconnect(self, protocol_type: str, client_name: str):
        pass

    def on_server_alive_for_client(self, protocol_type: str, client_name: str, is_alive:bool):
        pass