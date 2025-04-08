import datetime
import json
import logging
from os import path
from time import sleep
import pytest
from tests.helpers import *

from controller import Controller
from protocols import mqttclient
from tests.fake_mqtt_client import FakeMQTTClient

cmd_topic = "heatingcontrol/command"
response_topic = "heatingcontrol/on_cmd_response"
is_alive_topic = "heatingcontrol/serverdata/is_alive"
on_scheduler_topic = "heatingcontrol/serverdata/on_scheduler"
on_devices_topic = "heatingcontrol/serverdata/on_devices"
on_entities_topic = "heatingcontrol/serverdata/on_entities"

class TGHelpers:
    def publish_new_entity(entity:str, name:str):
        FakeMQTTClient.send_fake_message_raw('heat', 'homeassistant/climate/'+entity+'/state')
        FakeMQTTClient.send_fake_message_raw('5.0', 'homeassistant/climate/'+entity+'/min_temp')
        FakeMQTTClient.send_fake_message_raw('35.0', 'homeassistant/climate/'+entity+'/max_temp')
        FakeMQTTClient.send_fake_message_raw('19.0', 'homeassistant/climate/'+entity+'/temperature')
        FakeMQTTClient.send_fake_message_raw('20.3', 'homeassistant/climate/'+entity+'/current_temperature')
        FakeMQTTClient.send_fake_message_raw(name, 'homeassistant/climate/'+entity+'/friendly_name')
        FakeMQTTClient.send_fake_message_raw(datetime.datetime.now(datetime.timezone.utc).isoformat(), 'homeassistant/climate/'+entity+'/last_updated')
        FakeMQTTClient.send_fake_message_raw('true', 'homeassistant/climate/'+entity+'/restored')

    def create_device(devname:str, entity:str, publish_entity:bool, add_device:bool, caplog):
        # We first need to publish a new device entity to trigger auto-discovery in server
        # This will make the entity available to add a device
        if publish_entity:
            TGHelpers.publish_new_entity(entity, devname)

        if add_device:
            # Now we add a new device on this entity
            cmdname = "add_device"
            params = {"name": devname, "srventity": entity}
            FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
            assert response_topic in FakeMQTTClient.instance.published_messages
            assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
            check_no_error(caplog)

            # We check that the new device has been pushed to the remote clients by the server
            devices = json.loads(FakeMQTTClient.instance.published_messages[on_devices_topic])
            assert isinstance(devices, list)
            assert len(devices) == 1
            assert isinstance(devices[0], dict)
            assert 'name' in devices[0]
            assert devices[0]['name'] == devname
            assert devices[0]['srventity'] == entity
            FakeMQTTClient.instance.published_messages.clear()
        
        caplog.records.clear()

    def find_device(devices:list, dev_name:str)->dict:
        if isinstance(devices, list):
            for device in devices:
                if isinstance(device, dict) and 'name' in device and device['name']==dev_name:
                    return device
        return None
    

class TestGlobal:
    
    def __start_env(self):
        # removing config file to come back to default config file
        remove_file(path.join(config_path,'global_configuration.yaml'))
        FakeMQTTClient.replace_methods(mqttclient.MQTTClient)
        self.controller = Controller(config_path, 'global_')
        self.controller.start()
        assert FakeMQTTClient.instance != None and FakeMQTTClient.instance.deleted == False
        assert FakeMQTTClient.instance.bconnected==True
        assert is_alive_topic in FakeMQTTClient.instance.published_messages
        assert on_scheduler_topic in FakeMQTTClient.instance.published_messages
        assert on_devices_topic in FakeMQTTClient.instance.published_messages
        assert on_entities_topic in FakeMQTTClient.instance.published_messages
    
    def __stop_env(self):
        self.controller.stop()
        assert FakeMQTTClient.instance.bconnected==False
        assert FakeMQTTClient.instance.published_messages[is_alive_topic] == ''
        assert FakeMQTTClient.instance.deleted == True
        FakeMQTTClient.restore_methods(mqttclient.MQTTClient)
        # removing config file created by the server
        remove_file(path.join(config_path,'global_configuration.yaml'))
    
    # test if the complete server can start and stop without errors
    def test_server_init(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()
        self.__stop_env()
        check_no_error(caplog)

    def test_server_bad_mqtt_command(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        FakeMQTTClient.send_fake_message_raw("malformed message", cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"id": "MISSING_NODES"' in FakeMQTTClient.instance.published_messages[response_topic]

        FakeMQTTClient.instance.published_messages.clear()
        FakeMQTTClient.send_fake_message("badcommand", {}, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"id": "BAD_VALUE"' in FakeMQTTClient.instance.published_messages[response_topic]
        
        self.__stop_env()

    def test_server_missing_parameter(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        cmdlist = ["set_setpoint","set_device_name","add_device","set_device_entity",
                   "delete_device","set_active_schedule","delete_schedule","set_schedule_name","set_schedule_properties",
                   "set_schedule","set_scheduler_settings","set_tempset_name","set_tempsets"]

        params = {}
        for cmdname in cmdlist:
            FakeMQTTClient.instance.published_messages.clear()
            FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
            assert response_topic in FakeMQTTClient.instance.published_messages
            assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
            assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
            assert '"id": "MISSING_NODES"' in FakeMQTTClient.instance.published_messages[response_topic]

        # Special case : "set_devices_order" and "set_schedules_order" expect a list
        cmdlist = ["set_devices_order", "set_schedules_order"]
        for cmdname in cmdlist:
            FakeMQTTClient.instance.published_messages.clear()
            FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
            assert response_topic in FakeMQTTClient.instance.published_messages
            assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
            assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
            assert '"id": "BAD_VALUE"' in FakeMQTTClient.instance.published_messages[response_topic]

        self.__stop_env()
        
    def test_server_emptyorbad_parameter(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        TGHelpers.create_device('device#1', 'test-dev-entity#1', True, False, caplog)

        cmdlist = [("set_setpoint", {"device_name":"device#1", "setpoint":""}),
                   ("set_devices_order", ""),
                   ("set_device_name", {"old_name":"device#1", "new_name":""}),
                   ("add_device", {"name": "", "srventity": "test-dev-entity#1"}),
                   ("set_schedule_name", {"old_name": "schedule#1", "new_name": ""}),
                   ("set_schedule_properties", {"name": "schedule#1", "new_name": "", "parent":""}),
                   ("set_schedule", ""),
                   ("set_scheduler_settings", {"manual_mode_reset_event":""}),
                   ("set_scheduler_settings", {"manual_mode_reset_event":"value"}),
                   ("set_schedules_order", ""),
                   ("set_tempset_name", {"old_name":"tset#1", "new_name":"", "schedule_name":""}),
                   ("set_tempsets", {"temperature_sets":"", "schedule_name":""}),
                   ]

        for cmd in cmdlist:
            cmdname = cmd[0]
            params = cmd[1]
            FakeMQTTClient.instance.published_messages.clear()
            FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
            assert response_topic in FakeMQTTClient.instance.published_messages
            assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
            assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
            assert '"id": "BAD_VALUE"' in FakeMQTTClient.instance.published_messages[response_topic]

        self.__stop_env()

    def test_server_badreference(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        TGHelpers.create_device('device#1', 'test-dev-entity#1', True, False, caplog)

        cmdlist = [("set_setpoint", {"device_name":"", "setpoint":10.0}),
                   ("set_devices_order", ["dev"]),
                   ("set_device_name", {"old_name":"", "new_name":"dd"}),
                   ("add_device", {"name": "myname", "srventity": ""}),
                   ("set_device_entity", {"name": "", "new_srventity": "test-dev-entity#1"}),
                   ("set_device_entity", {"name": "device#1", "new_srventity": ""}),
                   ("delete_device", {"name": ""}),
                   ("delete_device", {"name": "my_device"}),
                   ("set_active_schedule", {"schedule_name":"my_schedule"}),
                   ("delete_schedule", {"schedule_name":"my_schedule"}),
                   ("set_schedule_name", {"old_name": "my_schedule", "new_name": "name"}),
                   ("set_schedule_properties", {"name": "my_schedule", "new_name": "name", "parent":""}),
                   ("set_tempset_name", {"old_name":"mytset", "new_name":"name", "schedule_name":""}),
                ]

        for cmd in cmdlist:
            cmdname = cmd[0]
            params = cmd[1]
            FakeMQTTClient.instance.published_messages.clear()
            FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
            assert response_topic in FakeMQTTClient.instance.published_messages
            assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
            assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
            assert '"id": "BAD_REFERENCE"' in FakeMQTTClient.instance.published_messages[response_topic]

        self.__stop_env()

    def test_server_duplicate_key(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        TGHelpers.create_device('device#1', 'test-dev-entity#1', True, False, caplog)

        cmdlist = [("set_device_name", {"old_name":"device#1", "new_name":"device#2"}),
                   ("add_device", {"name":"device#1", "srventity":"test-dev-entity#1"}),
                   ("set_schedule_name", {"old_name":"schedule#1", "new_name":"schedule#2"}),
                   ("set_schedule_properties", {"name":"schedule#1", "new_name":"schedule#2", "parent":""}),
                   ("set_tempset_name", {"old_name":"tset#1", "new_name":"tset#2", "schedule_name":""}),
                   ("set_tempsets", {"temperature_sets":[{'alias':'tset#1','devices':[]},{'alias':'tset#1','devices':[]}], "schedule_name":""}),
                ]
        
        for cmd in cmdlist:
            cmdname = cmd[0]
            params = cmd[1]
            FakeMQTTClient.instance.published_messages.clear()
            FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
            assert response_topic in FakeMQTTClient.instance.published_messages
            assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
            assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
            assert '"id": "DUPLICATE_UNIQUE_KEY"' in FakeMQTTClient.instance.published_messages[response_topic]

        self.__stop_env()

    def test_server_set_setpoint(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        # We check that the device exists
        devices = json.loads(FakeMQTTClient.instance.published_messages[on_devices_topic])
        assert TGHelpers.find_device(devices, "device#2")

        cmdname = "set_setpoint"
        params = {"device_name": "device#2", "setpoint":20.0}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog)

        #We check that a setpoint commnd has been sent to mqtt entity
        topic = 'homeassistant/climate/test-dev-entity#2/new_setpoint'
        assert topic in FakeMQTTClient.instance.published_messages
        assert FakeMQTTClient.instance.published_messages[topic] == '20.0'

        self.__stop_env()

    def test_server_delete_device(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        # We check that the device exists
        devices = json.loads(FakeMQTTClient.instance.published_messages[on_devices_topic])
        assert TGHelpers.find_device(devices, "device#2")

        cmdname = "delete_device"
        params = {"name": "device#2"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog)

        # We check that the device has been actually deleted
        devices = json.loads(FakeMQTTClient.instance.published_messages[on_devices_topic])
        assert TGHelpers.find_device(devices, "device#2") == None

        self.__stop_env()
        