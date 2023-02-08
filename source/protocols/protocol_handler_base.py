from .protocol_handler_callbacks import ProtocolHandlerCallbacks

class ProtocolHandlerBase:
    def __init__(self, clients_config: list, callbacks: ProtocolHandlerCallbacks):
        pass

    # return the string identifying this type of protocol in configuration file
    # (as child of the "protocols" node)
    def get_config_type() -> str:
        pass

    def get_client_from_name(self, client_name: str) -> object:
        pass

    def connect(self):
        pass

    def disconnect(self):
        pass

    # protocol_params content depends on the protocol handler implementation
    def send_message(self, client_name: str, protocol_params:dict):
        pass