__author__      = "Jérôme Cuq"

VERSION = '0.9.5'

## Standalone boilerplate before relative imports 
# For relative imports to work in Python 3.6
from pathlib import Path
import sys
import time
from command_repeater import CommandRepeater, PendingCommand
from errors import *

DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))

from configuration import Configuration
from protocols.protocols import Protocols
from protocols.protocol_handler_base import ProtocolHandlerBase
from protocols.protocol_handler_callbacks import ProtocolHandlerCallbacks
from protocols.mqttclient import MQTTClient
from device_interfaces.device_interfaces import DeviceInterfaces
from device_interfaces.device_interface_callbacks import DeviceInterfaceCallbacks
from scheduler import Scheduler, SchedulerCallbacks
from device import *
from remote.remote_control import RemoteControl
from remote.remote_control_callbacks import RemoteControlCallbacks

import logging
import logging.config
import yaml
import os

import common

class Controller(
        SchedulerCallbacks,
        ProtocolHandlerCallbacks,
        DeviceInterfaceCallbacks,
        RemoteControlCallbacks):
    
    def __init__(self, config_path:str = '.', config_files_prefix:str = ''):
        self.config_path:str = config_path
        self.config_files_prefix:str = config_files_prefix
        self.logger:logging.Logger = None
        self.remote_control: RemoteControl = None
        self.scheduler: Scheduler = None
        self.configuration: Configuration = None
        self.repeater: CommandRepeater = None
        self.protocols: Protocols = None
        self.devices: dict[str,Device] = {}
        self.device_interfaces: DeviceInterfaces = None

    def start(self):
        """
            :raises CfgError: in case of any error in parameters from configuration file
        """
        self.__init_logging()
        self.logger.info('Smart Heater server V'+VERSION)
        self.configuration = Configuration(self.config_path, self.config_files_prefix)
        self.repeater = CommandRepeater(self.configuration.get_repeater_delay())
        config_protocols = self.configuration.get_protocols()
        self.protocols = Protocols(config_protocols, self)

        # Instanciation of devices
        config_devices = self.configuration.get_devices()
        self.devices = {}
        # Create devices from config_devices and device_interface
        for devname in config_devices:
            devparams = config_devices[devname]
            prot = devparams['protocol']
            client_name = prot['name']
            protparams = prot['params']
            protocol_type = self.protocols.get_protocol_type_from_name(client_name)
            if protocol_type:
                self.devices[devname] = Device(devname, protocol_type, client_name, protparams)
            else:
                self.logger.error("ERROR: can not configure device '"+devname+"': protocol client '"+client_name+"' is not defined")

        self.device_interfaces = DeviceInterfaces(self.devices, self.configuration.get_auto_discovery(), self)

        config_remote = self.configuration.get_remote_control()
        self.remote_control = RemoteControl(config_remote, self.devices, self)
        self.remote_control.start()

        self.protocols.connect()

    def stop(self):
        self.logger.info('Stopping everything...')
        self.device_interfaces.on_server_alive(False)
        self.remote_control.stop()
        if self.repeater:
            self.repeater.stop()
            self.repeater = None
        if self.scheduler:
            self.scheduler.stop()
            self.scheduler = None
        self.protocols.disconnect()
        self.protocols = None

        self.remote_control = None
        self.configuration = None
        self.devices = {}
        self.device_interfaces = None
        self.logger.info('Server stopped')

    def __set_device_parameter(self, device_name:str, param_name:str, param_value, force_update: bool) -> CfgError:
        self.logger.debug("__set_device_parameter()")
        success:bool = device_name in self.devices
        if success:
            device:Device = self.devices[device_name]
            cmd:PendingCommand = self.repeater.getCommand(device_name, param_name)
            if param_name == 'setpoint':
                curSetpoint:float = device.setpoint
                if cmd and not force_update: curSetpoint = cmd.args[2]
                if force_update or (curSetpoint != param_value):
                    self.repeater.addCommand(device_name, param_name, self.device_interfaces.set_device_parameter, device, param_name, param_value)
                    self.device_interfaces.set_device_parameter(device, param_name, param_value)
                else:
                    self.logger.debug("__set_device_parameter() : setpoint is already good !")
            else:
                return CfgError(ECfgError.BAD_VALUE, "/devices['"+device_name+"']/params", None, {'value':param_name}, self.logger)
        else:
            return CfgError(ECfgError.BAD_REFERENCE, '/devices', None, {'reference':device_name}, self.logger)
        return None
    
    ################################################################################
    # Implementation of SchedulerCallbacks class
    ################################################################################
    # setpoints :
    #  - Each key is a device name, each value a temperature for setpoint
    #  - a None value means that the device has no scheduled setpoint
    #  - ALL known devices must have a defined setpoint
    def apply_devices_setpoints(self, setpoints: dict[str,float]):
        self.logger.info("Applying new setpoints : "+str(setpoints))
        first = True
        for device_name in setpoints:
            if device_name in self.devices:
                if not setpoints[device_name]:
                    self.devices[device_name].removeScheduledSetpoint()
                else:    
                    new_setpoint = common.toFloat(setpoints[device_name], self.logger, "Invalid parameter in apply_devices_setpoints() : ")
                    if new_setpoint:
                        if first==False: time.sleep(0.5)
                        first = False
                        self.devices[device_name].scheduled_setpoint = new_setpoint
                        self.__set_device_parameter(device_name, "setpoint", new_setpoint, False)
            else:
                self.logger.error("Can not change setpoint for unknown device '"+device_name+"'")
    ################################################################################
    # END OF SchedulerCallbacks implementation
    ################################################################################
    
    ################################################################################
    # Implementation of ProtocolHandlerCallbacks class
    ################################################################################
    def on_protocol_message(self, protocol_type: str, client_name: str, message):
        self.device_interfaces.on_client_message(protocol_type, client_name, message)
        self.remote_control.on_client_message(client_name, message)

    def on_protocol_connect(self, protocol_type: str, client_name: str):
        self.device_interfaces.on_client_connect(protocol_type, client_name)
        self.remote_control.on_client_connect(client_name)

        if not self.scheduler:
            # At least one protocol is available, so we can start the scheduler
            config_scheduler = self.configuration.get_scheduler()
            self.scheduler = Scheduler(config_scheduler,
                                       self, self.devices.keys(),
                                       self.configuration.get_scheduler_init_delai(),
                                       self.configuration.get_scheduler_manual_mode_reset_event())
        else:
            # We need to notify the scheduler about new accessible devices
            new_visible_devices = []
            for device in self.devices.values():
                if device.protocol_type == protocol_type and \
                   device.protocol_client_name == client_name:
                    new_visible_devices.append(device.name)
            if len(new_visible_devices)>0:
                self.scheduler.on_devices_connect(new_visible_devices)

    def on_protocol_disconnect(self, protocol_type: str, client_name: str):
        self.device_interfaces.on_client_disconnect(protocol_type, client_name)
        self.remote_control.on_client_disconnect(client_name)
    
    def on_server_alive_for_client(self, protocol_type: str, client_name: str, is_alive:bool):
        self.logger.info("Client['"+client_name+"']: server availability has changed to '"+str(is_alive)+"'")
        self.device_interfaces.on_server_alive_for_client(protocol_type, client_name, is_alive)
        self.remote_control.on_server_alive_for_client(client_name, is_alive)
    ################################################################################
    # END OF ProtocolHandlerCallbacks implementation
    ################################################################################

    ################################################################################
    # Implementation of DeviceInterfaceCallbacks class
    ################################################################################
    def on_device_state(self, device:Device, available:bool):
        if device.available != available:
            self.logger.info("Device['"+device.name+"']: availability state has changed to '"+str(available)+"'")
            device.available = available
            self.remote_control.on_device_state(device.name, available)
            if device.available==True and device.hasScheduledSetpoint()==True:
                self.logger.info("This device has a scheduled setpoint : "+str(device.scheduled_setpoint))
                self.__set_device_parameter(device.name, "setpoint", device.scheduled_setpoint, True)

    def on_device_current_temperature(self, device:Device, value:float):
        self.logger.debug("Device['"+device.name+"']: received current_temperature '"+str(value)+"'")
        device.current_temperature = value
        self.remote_control.on_device_current_temperature(device.name, value)

    def on_device_min_temperature(self, device:Device, value:float):
        self.logger.debug("Device['"+device.name+"']: received min_temperature '"+str(value)+"'")
        device.min_temperature = value
        self.remote_control.on_device_min_temperature(device.name, value)

    def on_device_max_temperature(self, device:Device, value:float):
        self.logger.debug("Device['"+device.name+"']: received max_temperature '"+str(value)+"'")
        device.max_temperature = value
        self.remote_control.on_device_max_temperature(device.name, value)

    def on_device_setpoint(self, device:Device, value:float):
        self.logger.debug("Device['"+device.name+"']: received setpoint '"+str(value)+"'")
        if device.setpoint != value:
            self.logger.info("Setpoint for device['"+device.name+"'] has changed. New value : '"+str(value)+"°'")
            device.setpoint = value
        self.repeater.removeCommand(device.name, 'setpoint')
        self.remote_control.on_device_setpoint(device.name, value)

    def on_discovered_device(self, device:Device):
        self.logger.debug("Device['"+device.name+"'] discovered !")
        err:CfgError = self.configuration.add_device(device.name, device.protocol_client_name, device.protocol_params)
        if not err:
            self.devices[device.name] = device
            # We need to notify devices consumers
            self.device_interfaces.on_devices(self.devices)
            self.remote_control.on_devices(self.devices)
        else:
            self.logger.error("Could not add invalid device")

    # protocol_msg_params content depends on the protocol handler implementation
    def send_message_to_device(self, device:Device, protocol_msg_params:dict):
        self.logger.debug("Sending msg to '"+device.name+"': "+str(protocol_msg_params))
        self.protocols.send_message(device.protocol_type, device.protocol_client_name, protocol_msg_params)

    def send_message_to_client(self, protocol_type:str, client_name:str, protocol_msg_params:dict):
        self.logger.debug("Sending msg to '"+client_name+"': "+str(protocol_msg_params))
        self.protocols.send_message(protocol_type, client_name, protocol_msg_params)
    ################################################################################
    # END OF DeviceInterfaceCallbacks implementation
    ################################################################################

    ################################################################################
    # Implementation of RemoteControlCallbacks class
    ################################################################################
    def get_protocol_type_from_name(self, client_name: str) -> str:
        return self.protocols.get_protocol_type_from_name(client_name)

    def get_client_by_name(self,client_name)-> object:
        return self.protocols.get_client_by_name(client_name)

    def get_scheduler_config(self) -> dict:
        return self.configuration.get_scheduler()

    def set_devices_order(self, remote_name:str, device_names:list):
        self.logger.info("[from '"+remote_name+"'] Received a new devices order : "+str(device_names))
        err:CfgError = self.configuration.set_devices_order(device_names)
        if not err:
            self.remote_control.on_server_response(remote_name, 'success')
            devices = {}
            for devname in device_names:
                devices[devname] = self.devices[devname]
            self.devices = devices
            # We need to notify devices consumers
            self.device_interfaces.on_devices(self.devices)
            self.remote_control.on_devices(self.devices)
        else:
            self.remote_control.on_server_response(remote_name, 'failure', err.to_dict())
            self.logger.error("Could not change devices order")

    def set_device_name(self, remote_name:str, old_name:str, new_name:str):
        self.logger.info("[from '"+remote_name+"'] Received name change for a device : '"+old_name+"' -> '"+new_name+"'")
        err:CfgError = self.configuration.change_device_name(old_name, new_name)
        if not err:
            self.remote_control.on_server_response(remote_name, 'success')
            # We update devices
            new_devs:dict[str,Device] = {}
            for name in self.devices:
                if name == old_name:
                    device:Device = self.devices[name]
                    device.name = new_name
                    new_devs[new_name] = device
                else:
                    new_devs[name] = self.devices[name]
            self.devices = new_devs
            # We need to notify devices consumers
            self.repeater.set_device_name(old_name, new_name)
            self.device_interfaces.on_devices(self.devices)
            self.remote_control.on_devices(self.devices)
            self.scheduler.on_devices(self.devices, self.configuration.get_scheduler())
            # something changed in scheduler data
            self.remote_control.on_scheduler(self.configuration.get_scheduler())
        else:
            self.remote_control.on_server_response(remote_name, 'failure', err.to_dict())
            self.logger.error("Could not change schedule name")

    def set_schedule(self, remote_name:str, schedule:dict):
        self.logger.info("[from '"+remote_name+"'] Received schedule '"+Configuration.get(schedule, 'alias','no-name')+"'")
        err:CfgError = self.configuration.set_schedule(schedule)
        if not err:
            self.remote_control.on_server_response(remote_name, 'success')
            # something changed in scheduler data
            self.scheduler.set_schedule(schedule)
            self.remote_control.on_scheduler(self.configuration.get_scheduler())
            
        else:
            self.remote_control.on_server_response(remote_name, 'failure', err.to_dict())
            self.logger.error("Could not set invalid schedule")

    def set_temperature_sets(self, remote_name:str, temperature_sets:list[dict], schedule_name:str):
        self.logger.info("[from '"+remote_name+"'] Received new temperature sets")
        err:CfgError = self.configuration.set_temperature_sets(temperature_sets, schedule_name)
        if not err:
            self.remote_control.on_server_response(remote_name, 'success')
            # something changed in scheduler data
            self.scheduler.set_scheduler(self.configuration.get_scheduler())
            self.remote_control.on_scheduler(self.configuration.get_scheduler())
        else:
            self.remote_control.on_server_response(remote_name, 'failure', err.to_dict())
            self.logger.error("Could not set invalid temperature sets")

    def set_temperature_set_name(self, remote_name:str, old_name:str, new_name:str, schedule_name:str):
        self.logger.info("[from '"+remote_name+"'] Received name change for a temperature set (schedule:'"+schedule_name+"')")
        err:CfgError = self.configuration.change_temperature_set_name(old_name, new_name, schedule_name)
        if not err:
            self.remote_control.on_server_response(remote_name, 'success')
            # something changed in scheduler data
            self.scheduler.set_scheduler(self.configuration.get_scheduler())
            self.remote_control.on_scheduler(self.configuration.get_scheduler())
        else:
            self.remote_control.on_server_response(remote_name, 'failure', err.to_dict())
            self.logger.error("Could not change temperature set name")

    def set_schedule_name(self, remote_name:str, old_name:str, new_name:str):
        self.logger.info("[from '"+remote_name+"'] Received name change for a schedule : '"+old_name+"' -> '"+new_name+"'")
        err:CfgError = self.configuration.change_schedule_name(old_name, new_name)
        if not err:
            self.remote_control.on_server_response(remote_name, 'success')
            # something changed in scheduler data
            self.scheduler.set_scheduler(self.configuration.get_scheduler())
            self.remote_control.on_scheduler(self.configuration.get_scheduler())
        else:
            self.remote_control.on_server_response(remote_name, 'failure', err.to_dict())
            self.logger.error("Could not change schedule name")

    def delete_schedule(self, remote_name:str, schedule_name:str):
        self.logger.info("[from '"+remote_name+"'] Received a deletion request for schedule : '"+schedule_name+"'")
        err:CfgError = self.configuration.delete_schedule(schedule_name)
        if not err:
            self.remote_control.on_server_response(remote_name, 'success')
            # something changed in scheduler data
            self.scheduler.set_scheduler(self.configuration.get_scheduler())
            self.remote_control.on_scheduler(self.configuration.get_scheduler())
        else:
            self.remote_control.on_server_response(remote_name, 'failure', err.to_dict())
            self.logger.error("Could not delete non existing schedule !")

    def set_active_schedule(self, remote_name:str, schedule_name:str):
        self.logger.info("[from '"+remote_name+"'] Received a new active schedule request ('"+schedule_name+"')")
        err:CfgError = self.configuration.set_active_schedule(schedule_name)
        if not err:
            self.remote_control.on_server_response(remote_name, 'success')
            # something changed in scheduler data
            self.scheduler.on_active_schedule_changed()
            self.remote_control.on_scheduler(self.configuration.get_scheduler())
        else:
            self.remote_control.on_server_response(remote_name, 'failure', err.to_dict())
            self.logger.error("Could not change active schedule")

    def set_schedules_order(self, remote_name:str, schedule_names:list):
        self.logger.info("[from '"+remote_name+"'] Received a new schedules order : "+str(schedule_names))
        err:CfgError = self.configuration.set_schedules_order(schedule_names)
        if not err:
            self.remote_control.on_server_response(remote_name, 'success')
        else:
            self.remote_control.on_server_response(remote_name, 'failure', err.to_dict())
            self.logger.error("Could not change schedules order")

    # Ask for a device parameter change
    # param_name may be either :
    # - 'setpoint' : param_value must be a float.
    def set_device_parameter(self, remote_name:str, device_name, param_name, param_value):
        err:CfgError = self.__set_device_parameter(device_name, param_name, param_value, False)
        if not err:
            self.remote_control.on_server_response(remote_name, 'success')
        else:
            self.remote_control.on_server_response(remote_name, 'failure', err.to_dict())
            self.logger.error("Could not set device parameter")
    ################################################################################
    # END OF RemoteControlCallbacks implementation
    ################################################################################


    ################################################################################
    # PRIVATE METHODS
    ################################################################################

    def __init_logging(self):
        config_file = open(os.path.join(self.config_path, self.config_files_prefix+'logging.yaml'), 'r')
        logging_config = yaml.load(config_file,Loader=yaml.Loader)
        logging.config.dictConfig(logging_config)
        self.logger = logging.getLogger('hcs.controller')

    # return True if all clients used by devices are connected
    def __are_all_devices_connected(self):
        connected = []
        for device in self.devices.values():
            if not (device.protocol_client_name in connected):
                if not self.protocols.is_connected(device.protocol_type, device.protocol_client_name):
                    return False
                connected.append(device.protocol_client_name)
        return True