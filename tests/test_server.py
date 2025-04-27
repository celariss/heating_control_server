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
from tests.test_server_helpers import *
   

class TestServer:
    
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
        check_no_error(caplog, True)

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
        assert '"cmd": "badcommand"' in FakeMQTTClient.instance.published_messages[response_topic]
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

        TSHelpers.create_device('device#1', 'test-dev-entity#1', True, False, caplog)

        cmdlist = [("set_setpoint", {"device_name":"device#1", "setpoint":""}),
                   ("set_devices_order", ""),
                   ("set_device_name", {"old_name":"device#1", "new_name":""}),
                   ("add_device", {"name": "", "srventity": "test-dev-entity#1"}),
                   ("set_schedule_name", {"old_name": "schedule#1", "new_name": ""}),
                   ("set_schedule_properties", {"name": "schedule#1", "new_name": "", "parent":""}),
                   ("set_schedule", ""),
                   ("set_scheduler_settings", {"manual_mode_reset_event":""}),
                   ("set_scheduler_settings", {"manual_mode_reset_event":"value"}),
                   ("set_scheduler_settings", {"manual_mode_reset_event":0}),
                   ("set_scheduler_settings", {"manual_mode_reset_event":25}),
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

        TSHelpers.create_device('device#1', 'test-dev-entity#1', True, False, caplog)

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
                   ("set_schedule_properties", {"name": "schedule#1", "new_name": "name", "parent":"my_schedule"}),
                   ("set_schedules_order", ["test"]),
                   ("set_schedules_order", ["schedule#1", "test"]),
                   ("set_tempset_name", {"old_name":"mytset", "new_name":"name", "schedule_name":""}),
                   ("set_tempset_name", {"old_name":"tset#1", "new_name":"name", "schedule_name":"schedule"}),
                   ("set_tempset_name", {"old_name":"tset#1", "new_name":"name", "schedule_name":"schedule#3"}),
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

        TSHelpers.create_device('device#1', 'test-dev-entity#1', True, False, caplog)

        cmdlist = [("set_device_name", {"old_name":"device#1", "new_name":"device#2"}),
                   ("add_device", {"name":"device#1", "srventity":"test-dev-entity#1"}),
                   ("set_schedule_name", {"old_name":"schedule#1", "new_name":"schedule#2"}),
                   ("set_schedule_properties", {"name":"schedule#1", "new_name":"schedule#2", "parent":""}),
                   ("set_tempset_name", {"old_name":"tset#1", "new_name":"tset#2", "schedule_name":""}),
                   ("set_tempset_name", {"old_name":"sch3_tset#1", "new_name":"sch3_tset#2", "schedule_name":"schedule#3"}),
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
        assert TSHelpers.find_device("device#2")

        cmdname = "set_setpoint"
        params = {"device_name": "device#2", "setpoint":20.0}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        #We check that a setpoint commnd has been sent to mqtt entity
        topic = 'homeassistant/climate/test-dev-entity#2/new_setpoint'
        assert topic in FakeMQTTClient.instance.published_messages
        assert FakeMQTTClient.instance.published_messages[topic] == '20.0'

        self.__stop_env()

    def test_server_set_devices_order(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        # We check the devices order
        devices = json.loads(FakeMQTTClient.instance.published_messages[on_devices_topic])
        assert len(devices)==3
        assert devices[0]['name'] == "device#1"
        assert devices[1]['name'] == "device#2"
        assert devices[2]['name'] == "device#3"

        # Checking error detection (missing device#1 in list)
        cmdname = "set_devices_order"
        params = ["device#2", "device#3"]
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"id": "MISSING_VALUE"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"value": "device#1"' in FakeMQTTClient.instance.published_messages[response_topic]

        caplog.records.clear()
        cmdname = "set_devices_order"
        params = ["device#2", "device#1", "device#3"]
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        # We check the new order
        devices = json.loads(FakeMQTTClient.instance.published_messages[on_devices_topic])
        assert len(devices)==3
        assert devices[0]['name'] == "device#2"
        assert devices[1]['name'] == "device#1"
        assert devices[2]['name'] == "device#3"

        self.__stop_env()

    def test_set_device_name(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        # We check the number of references to device#1
        count = TSHelpers.count_dev_references("device#1")
        assert count > 1

        cmdname = "set_device_name"
        params = {"old_name": "device#1", "new_name": "my_device"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        # We check that the device has been actually renamed
        # 1) There is no occurence of device#1 left anywhere in configuration
        assert TSHelpers.count_dev_references("device#1") == 0
        # 2) The new device name exists
        assert TSHelpers.find_device("my_device")
        # 2) Every device reference has been renamed
        assert TSHelpers.count_dev_references("my_device") == count

        self.__stop_env()

    def test_add_device(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()
        TSHelpers.create_device("my_device", "my_entity", True, True, caplog)
        self.__stop_env()

    def test_set_device_entity(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        # publishing a new device entity
        TSHelpers.create_device("my_device", "my_entity", True, False, caplog)

        cmdname = "set_device_entity"
        params = {"name": "device#1", "new_srventity": "my_entity"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        # Checking 
        device = TSHelpers.find_device("device#1")
        assert isinstance(device, dict)
        assert device['srventity'] == "my_entity"
        
        self.__stop_env()
    
    def test_server_delete_device(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        # We check that the devices exist
        assert TSHelpers.find_device("device#1")
        assert TSHelpers.find_device("device#2")

        # We try to delete a device that is referenced in scheduler
        cmdname = "delete_device"
        params = {"name": "device#1"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"id": "REFERENCED_NODE"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"node": "device#1"' in FakeMQTTClient.instance.published_messages[response_topic]
        caplog.records.clear()

        cmdname = "delete_device"
        params = {"name": "device#2"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        # We check that the device has been actually deleted
        assert TSHelpers.find_device("device#2") == None

        self.__stop_env()
        
    def test_set_active_schedule(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()
        
        TSHelpers.change_active_schedule("schedule#2", caplog)

        cmdname = "delete_schedule"
        params = {"schedule_name": "schedule#2"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]

        TSHelpers.change_active_schedule("", caplog)

        self.__stop_env()

    def test_delete_schedule(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()
        
        # We change the active schedule
        TSHelpers.change_active_schedule("schedule#2", caplog)

        # Trying to delete the schedule#1
        cmdname = "delete_schedule"
        params = {"schedule_name": "schedule#1"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"id": "REFERENCED_NODE"' in FakeMQTTClient.instance.published_messages[response_topic]
        caplog.records.clear()

        # Now we delete the schedule#2
        cmdname = "delete_schedule"
        params = {"schedule_name": "schedule#2"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        # We check that schedule#2 has been deleted
        assert TSHelpers.find_schedule("schedule#2") == None
        # We check that there is no active schedule anymore
        assert TSHelpers.get_active_schedule_name() == None

        self.__stop_env()

    def test_set_schedule_name(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        # We change the active schedule
        TSHelpers.change_active_schedule("schedule#1", caplog)

        # Now we rename the schedule#1
        cmdname = "set_schedule_name"
        params = {"old_name": "schedule#1", "new_name": "my_schedule"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        # We check that :
        # - the schedule has been renamed
        # - the active schedule has been renamed
        # - the schedule#2 parent has been renamed
        assert TSHelpers.find_schedule("schedule#1") == None
        assert TSHelpers.find_schedule("my_schedule")
        assert TSHelpers.get_active_schedule_name() == "my_schedule"
        schedule2 = TSHelpers.find_schedule("schedule#2")
        assert schedule2 and 'parent_schedule' in schedule2 and schedule2['parent_schedule']=="my_schedule"

        self.__stop_env()

    def test_set_schedule_properties(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        cmdname = "set_schedule_properties"
        params = {"name": "schedule#1", "new_name": "schedule#1", "parent":"schedule#2"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"id": "CIRCULAR_REF"' in FakeMQTTClient.instance.published_messages[response_topic]
        caplog.records.clear()

        # We change the active schedule
        TSHelpers.change_active_schedule("schedule#1", caplog)

        # Then we rename the schedule#1
        cmdname = "set_schedule_properties"
        params = {"name": "schedule#1", "new_name": "my_schedule", "parent":""}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        # We check that :
        # - the schedule has been renamed
        # - the active schedule has been renamed
        # - the schedule#2 parent has been renamed
        assert TSHelpers.find_schedule("schedule#1") == None
        assert TSHelpers.find_schedule("my_schedule")
        assert TSHelpers.get_active_schedule_name() == "my_schedule"
        schedule2 = TSHelpers.find_schedule("schedule#2")
        assert schedule2 and 'parent_schedule' in schedule2 and schedule2['parent_schedule']=="my_schedule"

        # Now we change the parent of schedule#3
        cmdname = "set_schedule_properties"
        params = {"name": "schedule#3", "new_name": "schedule#3", "parent":"schedule#2"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        schedule3 = TSHelpers.find_schedule("schedule#3")
        assert schedule3 and 'parent_schedule' in schedule3 and schedule3['parent_schedule']=="schedule#2"

        self.__stop_env()

    def test_set_schedule(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        schedule3 = TSHelpers.find_schedule("schedule#3")
        assert schedule3
        schedule3['parent_schedule'] = 'schedule#2'

        cmdname = "set_schedule"
        params = schedule3
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        schedule3 = TSHelpers.find_schedule("schedule#3")
        assert schedule3
        assert schedule3['parent_schedule'] == 'schedule#2'

        schedule3['alias'] = 'schedule#4'
        cmdname = "set_schedule"
        params = schedule3
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        schedule4 = TSHelpers.find_schedule("schedule#4")
        assert schedule4
        assert schedule4['parent_schedule'] == 'schedule#2'

        self.__stop_env()

    def test_set_schedule_settings(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        cmdname = "set_scheduler_settings"
        params = {"manual_mode_reset_event": 2}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        cmdname = "set_scheduler_settings"
        params = {"manual_mode_reset_event": "timeslot_change"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        cmdname = "set_scheduler_settings"
        params = {"manual_mode_reset_event": "setpoint_change"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        self.__stop_env()

    def test_set_schedules_order(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        cmdname = "set_schedules_order"
        params = ["schedule#1", "schedule#3", "schedule#2", "schedule#4"]
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        schedules = TSHelpers.get_schedules()
        assert schedules[0]['alias'] == "schedule#1"
        assert schedules[1]['alias'] == "schedule#3"
        assert schedules[2]['alias'] == "schedule#2"
        assert schedules[3]['alias'] == "schedule#4"

        cmdname = "set_schedules_order"
        params = ["schedule#1", "schedule#3"]
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"id": "MISSING_VALUE"' in FakeMQTTClient.instance.published_messages[response_topic]

        self.__stop_env()

    def test_set_tempset_name_global(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        # We check the number of references to tset#1
        count = TSHelpers.count_global_tempset_references("tset#1")
        assert count > 1

        cmdname = "set_tempset_name"
        params = {"old_name": "tset#1", "new_name":"my_tset", "schedule_name":""}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        assert TSHelpers.count_global_tempset_references("tset#1") == 0
        # schedule#4 has a local temperature set named tset#1, 
        # so the local references in schedule items must not have been renamed
        for item in TSHelpers.find_schedule('schedule#4')['schedule_items']:
            for timeslot_set in item['timeslots_sets']:
                for timeslot in TSHelpers.get_all_timeslots(timeslot_set):
                    assert timeslot['temperature_set'] != "my_tset"
        assert TSHelpers.count_global_tempset_references("my_tset") == count

        self.__stop_env()

    def test_set_tempset_name_local(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        # We check the number of references to global tset#1
        count = TSHelpers.count_global_tempset_references("tset#1")
        assert count > 1
        assert TSHelpers.count_global_tempset_references("my_tset") == 0

        cmdname = "set_tempset_name"
        params = {"old_name": "tset#1", "new_name":"my_tset", "schedule_name":"schedule#4"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        assert TSHelpers.count_global_tempset_references("tset#1") == count
        assert TSHelpers.count_global_tempset_references("my_tset") == 0
        # schedule#4 has a local temperature set named tset#1 that must have been renamed
        schedule4 = TSHelpers.find_schedule('schedule#4')
        for item in schedule4['schedule_items']:
            for timeslot_set in item['timeslots_sets']:
                for timeslot in TSHelpers.get_all_timeslots(timeslot_set):
                    assert timeslot['temperature_set'] != "tset#1"
        assert TSHelpers.count_local_tempset_references(schedule4, "my_tset") == 2
        
        self.__stop_env()

    def test_set_tempsets(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        cmdname = "set_tempsets"
        params = {"temperature_sets": [{'alias': 'tset#2', 'devices': [{'device_name': 'device#1', 'setpoint': 16.0}]},
                                       {'alias': 'tset#1', 'devices': [{'device_name': 'device#1', 'setpoint': 13.0}]}],
                "schedule_name":""}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        cmdname = "set_tempsets"
        params = {"temperature_sets": [{'alias': 'sch4_tset#2', 'devices': [{'device_name': 'device#1', 'setpoint': 16.0}]},
                                       {'alias': 'sch4_tset#3', 'devices': [{'device_name': 'device#1', 'setpoint': 13.0}]}],
                "schedule_name":"schedule#4"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)

        cmdname = "set_tempsets"
        params = {"temperature_sets": [{'alias': 'tset#2', 'devices': [{'device_name': 'device#1', 'setpoint': 16.0}]},
                                       {'alias': 'tset#3', 'devices': [{'device_name': 'device#1', 'setpoint': 13.0}]}],
                "schedule_name":""}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"id": "BAD_REFERENCE"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"reference": "tset#1"' in FakeMQTTClient.instance.published_messages[response_topic]

        cmdname = "set_tempsets"
        params = {"temperature_sets": [{'alias': 'tset#2', 'devices': [{'device_name': 'device#1', 'setpoint': 16.0}]}],
                "schedule_name":"schedule#4"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"id": "BAD_REFERENCE"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"reference": "sch4_tset#2"' in FakeMQTTClient.instance.published_messages[response_topic]

        self.__stop_env()