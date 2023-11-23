__author__      = "Jérôme Cuq"

from datetime import datetime


class Device:
    def __init__(self, dev_name:str, protocol_type:str, protocol_client_name:str, protocol_params: dict):
        self.name:str = dev_name
        self.protocol_type:str = protocol_type
        self.protocol_client_name:str = protocol_client_name
        self.protocol_params:dict = protocol_params
        self.current_temperature:float = 0.0
        self.min_temperature:float = 5.0
        self.max_temperature:float = 35.0
        self.setpoint:float = 0.0
        self.scheduled_setpoint:float = None
        self.available:bool = False
        self.last_updated:datetime = datetime.fromisoformat("1000-01-01T01:00:00.000000+00:00")

    def hasScheduledSetpoint(self) -> bool:
        return self.scheduled_setpoint != None

    def removeScheduledSetpoint(self):
        self.scheduled_setpoint:float = None