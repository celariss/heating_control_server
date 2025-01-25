__author__      = "Jérôme Cuq"

from device import Device

class RemoteControlCallbacks:
    def get_protocol_type_from_name(self, client_name: str) -> str:
        pass

    def get_client_by_name(self,client_name)-> object:
        pass

    def get_scheduler_config(self) -> dict:
        pass

    def set_devices_order(self, remote_name:str, device_names:list):
        pass

    def set_device_name(self, remote_name:str, old_name:str, new_name:str):
        pass

    def add_device(self, remote_name:str, name:str, srventity:str):
        pass

    def set_device_entity(self, remote_name:str, name:str, new_srventity:str):
        pass

    def delete_device(self, remote_name:str, name:str):
        pass

    def set_scheduler_settings(self, remote_name:str, settings:dict):
        pass

    def set_schedule(self, remote_name:str, schedule:dict):
        pass

    def set_temperature_sets(self, remote_name:str, temperature_sets:dict, schedule_name:str):
        pass

    def set_temperature_set_name(self, remote_name:str, old_name:str, new_name:str, schedule_name:str):
        pass

    def set_schedule_name(self, remote_name:str, old_name:str, new_name:str):
        pass

    # Change properties of schedule named 'name'
    # 'new_name' may or may not be different from 'name'
    def set_schedule_properties(self, remote_name:str, name:str, new_name:str, parent:str):
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