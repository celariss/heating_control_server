__author__      = "Jérôme Cuq"

from device import Device
from protocols.mqttclient import MQTTClient

class RemoteControlCallbacks:
    def get_protocol_type_from_name(self, client_name: str) -> str:
        pass

    def get_client_by_name(self,client_name)-> MQTTClient:
        pass

    def get_scheduler_config(self) -> dict:
        pass

    def set_schedule(self, remote_name:str, schedule:dict):
        pass

    def set_temperature_sets(self, remote_name:str, temperature_sets:dict, schedule_name:str):
        pass

    def set_temperature_set_name(self, remote_name:str, old_name:str, new_name:str, schedule_name:str):
        pass

    def set_schedule_name(self, remote_name:str, old_name:str, new_name:str):
        pass

    def delete_schedule(self, remote_name:str, schedule_name:str):
        pass
    
    def set_active_schedule(self, remote_name:str, schedule_name:str):
        pass

    def set_schedules_order(self, remote_name:str, schedule_names:list):
        pass

    # Ask for a device parameter change
    # param_name may be either :
    # - 'setpoint' : param_value must be a float.
    def set_device_parameter(self, remote_name:str, device_name, param_name, param_value):
        pass