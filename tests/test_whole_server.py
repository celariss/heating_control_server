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

        FakeMQTTClient.send_fake_message_raw("badcommand", cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"id": "EXCEPTION"' in FakeMQTTClient.instance.published_messages[response_topic]

        FakeMQTTClient.instance.published_messages.clear()
        FakeMQTTClient.send_fake_message("badcommand", {}, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"id": "BAD_VALUE"' in FakeMQTTClient.instance.published_messages[response_topic]
        
        self.__stop_env()

    def test_server_err_add_device(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        cmdname = "add_device"
        params = {}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert "command: add_device" in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"id": "BAD_VALUE"' in FakeMQTTClient.instance.published_messages[response_topic]
        
        cmdname = "add_device"
        params = {"name": "", "srventity": "my-entity"}
        FakeMQTTClient.instance.published_messages.clear()
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"id": "MISSING_VALUE"' in FakeMQTTClient.instance.published_messages[response_topic]

        cmdname = "add_device"
        params = {"name": "test-dev", "srventity": "srv/test-dev"}
        FakeMQTTClient.instance.published_messages.clear()
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "failure"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"id": "BAD_REFERENCE"' in FakeMQTTClient.instance.published_messages[response_topic]
 
        self.__stop_env()

    def test_server_add_device(self, caplog):
        caplog.set_level(logging.INFO)
        self.__start_env()

        # We first need to publish a new device entity to trigger auto-discovery in server
        # This will make the entity available to add a device
        FakeMQTTClient.publish_new_device('test-dev', 'Test Device')

        # Now we add a new device on this entity
        cmdname = "add_device"
        params = {"name": "Room#1", "srventity": "test-dev"}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]

        # We check that the new device has been pushed to the remote clients by the server
        devices = json.loads(FakeMQTTClient.instance.published_messages[on_devices_topic])
        assert isinstance(devices, list)
        assert len(devices) == 1
        assert isinstance(devices[0], dict)
        assert 'name' in devices[0]
        assert devices[0]['name'] == 'Room#1'
        assert devices[0]['srventity'] == 'test-dev'
        
        self.__stop_env()
        check_no_error(caplog)